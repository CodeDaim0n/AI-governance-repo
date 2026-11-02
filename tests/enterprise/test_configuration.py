"""Configuration contracts with simulated HTTP, model and storage responses.

These tests do not claim live product integration, Fairlearn execution or
PostgreSQL acceptance. Optional metric computation is explicitly simulated.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import httpx

from fabric.enterprise.clients import DependencyFailure, GLPI, Keycloak, MLflowRegistry, OpenFGA, OpenMetadata
from fabric.enterprise.configuration import (
    ConfigurationError, allowed_principals, dispatch_storage_mode,
    enforce_metric_requirements, metric_requirements, workflow_risk_bindings,
)
from fabric.enterprise import dispatch, evaluate


class NativeConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            **{name: os.environ[name] for name in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP') if name in os.environ},
            'FGA_URL': 'http://fga.local', 'FGA_TOKEN': 'simulated-token',
            'FGA_STORE_ID': 'store', 'FGA_MODEL_ID': 'model',
            'METADATA_URL': 'http://metadata.local/api', 'METADATA_TOKEN': 'simulated-token',
            'METADATA_TABLE_FQN': 'fabric.credit.public.cases', 'METADATA_REQUIRED_TAG': 'PII.Sensitive',
            'GLPI_URL': 'http://glpi.local/api', 'GLPI_APP_TOKEN': 'simulated-token',
            'GLPI_USER_TOKEN': 'simulated-token', 'GLPI_SERVICE_ID': '7', 'GLPI_ENTITY_ID': '2',
            'MODEL_NAME': 'configured-model', 'MLFLOW_URL': 'http://mlflow.local',
            'FAIRNESS_MAX_DIFFERENCE': '0.2', 'DATABASE_URL': 'simulated-storage',
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def http_client(self, cls, handler):
        if cls is GLPI:
            with patch('fabric.enterprise.clients.API.call', return_value={'session_token': 'simulated-session'}):
                client = cls()
        else:
            client = cls()
        client.client.close()
        client.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
        self.addCleanup(client.client.close)
        return client

    def registry(self, metrics, expiry=None):
        registry = MLflowRegistry.__new__(MLflowRegistry)
        registry.client = MagicMock()
        registry.client.get_model_version_by_alias.return_value = SimpleNamespace(run_id='run', version='2')
        registry.client.get_run.return_value = SimpleNamespace(data=SimpleNamespace(
            metrics=metrics, tags={'fabric.independent_approval': 'true',
                                  'fabric.validation_expires': str(time.time() + 300) if expiry is None else expiry}))
        return registry

    def test_default_and_configured_signed_claim_principals(self):
        self.assertIn('agent-a', allowed_principals())
        identity = Keycloak.__new__(Keycloak)
        identity.issuer = 'simulated-issuer'
        identity.jwt = MagicMock()
        identity.jwks = MagicMock()
        with patch.dict(os.environ, {'FABRIC_ALLOWED_PRINCIPALS_JSON': '["ops-bot","ops-reviewer"]'}):
            identity.jwt.decode.return_value = {'fabric_principal': 'ops-bot'}
            self.assertEqual(identity.verify('simulated-verified-token'), 'ops-bot')
            identity.jwt.decode.return_value = {'fabric_principal': 'agent-a'}
            with self.assertRaises(DependencyFailure):
                identity.verify('simulated-verified-token')

    def test_invalid_principal_configuration_never_falls_back(self):
        for value in ('', '[]', '{}', '["a","a"]', '[true]', '[" "]'):
            with self.subTest(value=value), patch.dict(os.environ, {'FABRIC_ALLOWED_PRINCIPALS_JSON': value}):
                with self.assertRaises(ConfigurationError):
                    allowed_principals()

    def test_fga_environment_and_per_workflow_types(self):
        payloads = []
        client = self.http_client(OpenFGA, lambda r: (payloads.append(json.loads(r.content))
                                                       or httpx.Response(200, json={'allowed': True})))
        with patch.dict(os.environ, {'FGA_USER_TYPE': 'employee', 'FGA_OBJECT_TYPE': 'invoice', 'FGA_RELATION': 'submitter'}):
            self.assertTrue(client.check('alice', 'inv-4'))
            self.assertTrue(client.check('alice', 'service-2', object_type='service', relation='requester', user_type='person'))
        self.assertEqual(payloads[0]['tuple_key'], {'user': 'employee:alice', 'relation': 'submitter', 'object': 'invoice:inv-4'})
        self.assertEqual(payloads[1]['tuple_key'], {'user': 'person:alice', 'relation': 'requester', 'object': 'service:service-2'})
        self.assertEqual(payloads[1]['authorization_model_id'], 'model')
        self.assertEqual(payloads[1]['consistency'], 'HIGHER_CONSISTENCY')

    def test_invalid_fga_binding_is_rejected_before_http(self):
        client = self.http_client(OpenFGA, lambda r: self.fail('Invalid configuration must not reach HTTP'))
        for value in ('', '../case', 'case:admin', 'case#owner'):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                client.check('alice', 'resource', object_type=value)
        with self.assertRaises(ConfigurationError):
            client.check('alice#admin', 'resource')
        with patch.dict(os.environ, {'FGA_OBJECT_TYPE': 'invoice'}), self.assertRaises(ConfigurationError):
            client.bootstrap()

    def test_metadata_custom_entity_and_lineage_types(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={'id': 'entity', 'version': 3,
                                           'owners': [{'id': 'owner'}], 'tags': [{'tagFQN': 'Governed.Internal'}]})
        client = self.http_client(OpenMetadata, handler)
        with patch.dict(os.environ, {'METADATA_ENTITY_TYPE': 'pipeline', 'METADATA_ENTITY_COLLECTION': 'pipelines',
                                     'METADATA_ENTITY_FQN': 'service.pipeline', 'METADATA_REQUIRED_TAG': 'Governed.Internal'}):
            self.assertEqual(client.assert_classified()['version'], 3)
            client.lineage('source', 'target')
        self.assertEqual(requests[0].url.path, '/api/v1/pipelines/name/service.pipeline')
        edge = json.loads(requests[1].content)['edge']
        self.assertEqual(edge['fromEntity']['type'], 'pipeline')
        self.assertEqual(edge['toEntity']['type'], 'pipeline')

    def test_metadata_overrides_still_require_owner_and_classification(self):
        requests = []
        client = self.http_client(OpenMetadata, lambda r: (requests.append(r)
            or httpx.Response(200, json={'id': 'entity', 'owners': [], 'tags': [{'tagFQN': 'Governed.Internal'}]})))
        with self.assertRaises(DependencyFailure):
            client.assert_classified(entity_type='topic', entity_collection='topics', entity_fqn='service.topic',
                                     required_tag='Governed.Internal')
        self.assertEqual(requests[0].url.path, '/api/v1/topics/name/service.topic')
        with patch.dict(os.environ, {'METADATA_ENTITY_TYPE': 'topic'}), self.assertRaises(ConfigurationError):
            client.assert_classified()
        self.assertEqual(len(requests), 1)

    def test_glpi_custom_type_preserves_entity_scope(self):
        requests = []
        client = self.http_client(GLPI, lambda r: (requests.append(r) or httpx.Response(200, json={'id': 7, 'entities_id': 2})))
        with patch.dict(os.environ, {'GLPI_SERVICE_TYPE': 'Software'}):
            self.assertEqual(client.service()['id'], 7)
        self.assertEqual(requests[0].url.path, '/api/Software/7')
        with self.assertRaises(DependencyFailure):
            client.service(service_type='NetworkEquipment', service_id='9', entity_id='3')
        self.assertEqual(requests[1].url.path, '/api/NetworkEquipment/9')
        with self.assertRaises(ConfigurationError):
            client.service(service_type='../Ticket')
        self.assertEqual(len(requests), 2)

    def test_configured_metric_gates_and_boundaries(self):
        gates = {'accuracy': {'min': 0.8}, 'latency_seconds': {'min': 0, 'max': 2}}
        with patch.dict(os.environ, {'MODEL_METRIC_REQUIREMENTS_JSON': json.dumps(gates)}):
            self.assertEqual(enforce_metric_requirements({'accuracy': 0.8, 'latency_seconds': 2}), gates)
            self.assertEqual(self.registry({'accuracy': 0.9, 'latency_seconds': 1.5}).validate()['run_id'], 'run')
            for metrics in ({'accuracy': 0.7, 'latency_seconds': 1}, {'accuracy': 0.9, 'latency_seconds': 3}, {'accuracy': 0.9}):
                with self.subTest(metrics=metrics), self.assertRaises(DependencyFailure):
                    self.registry(metrics).validate()

    def test_missing_nonfinite_and_wrong_type_metrics_fail_both_gates(self):
        for value in (None, '0.1', True, float('nan'), float('inf'), float('-inf')):
            metrics = {} if value is None else {'fairness_difference': value}
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError):
                    enforce_metric_requirements(metrics)
                with self.assertRaises(DependencyFailure):
                    self.registry(metrics).validate()

    def test_invalid_metric_configuration_never_falls_back(self):
        for raw in ('', '{}', '[]', '{"accuracy":{}}', '{"accuracy":{"minimum":1}}',
                    '{"accuracy":{"min":true}}', '{"accuracy":{"max":NaN}}',
                    '{"accuracy":{"min":1,"max":0}}', '{"accuracy":{"max":1,"max":2}}'):
            with self.subTest(raw=raw), patch.dict(os.environ, {'MODEL_METRIC_REQUIREMENTS_JSON': raw}):
                with self.assertRaises(ConfigurationError):
                    metric_requirements()
        for raw in ('NaN', 'Infinity', '', 'invalid'):
            with self.subTest(raw=raw), patch.dict(os.environ, {'FAIRNESS_MAX_DIFFERENCE': raw}):
                with self.assertRaises(ConfigurationError):
                    metric_requirements()

    def test_invalid_expiry_does_not_pass_model_gate(self):
        for expiry in ('nan', 'inf', '-inf', ''):
            with self.subTest(expiry=expiry), self.assertRaises(DependencyFailure):
                self.registry({'fairness_difference': 0}, expiry).validate()

    def test_per_workflow_model_and_metric_gates_preserve_release_checks(self):
        registry = self.registry({'accuracy': 0.9})
        self.assertEqual(registry.validate(model_name='access-proposal', metric_requirements={'accuracy': {'min': 0.8}})['model_version'], '2')
        registry.client.get_model_version_by_alias.assert_called_once_with('access-proposal', 'validated')
        registry.client.get_run.return_value.data.tags['fabric.independent_approval'] = 'false'
        with self.assertRaises(DependencyFailure):
            registry.validate(model_name='access-proposal', metric_requirements={'accuracy': {'min': 0.8}})

    def test_publication_preserves_candidate_and_dataset_provenance(self):
        registry = self.registry({'accuracy': 1})
        mlflow = MagicMock()
        mlflow.start_run.return_value.__enter__.return_value.info.run_id = 'evaluation-run'
        registry.client.create_model_version.return_value = SimpleNamespace(version='3')
        with patch.dict('sys.modules', {'mlflow': mlflow}):
            registry.publish_evaluation({'accuracy': 1}, {'dataset': 'provided-validation-set', 'dataset_origin': 'operator_supplied'})
        self.assertEqual(mlflow.set_tags.call_args.args[0]['fabric.independent_approval'], 'false')
        self.assertEqual(mlflow.set_tags.call_args.args[0]['fabric.dataset'], 'provided-validation-set')
        registry.client.set_registered_model_alias.assert_called_once_with('configured-model', 'candidate', '3')

    def test_dispatch_risk_mapping_and_storage_choice(self):
        self.assertEqual(dispatch.risk_ids(['tenant_boundary'], 'denied'), ['R01'])
        self.assertEqual(dispatch_storage_mode(), 'legacy')
        with patch.dict(os.environ, {'FABRIC_DISPATCH_RISK_MAP_JSON': '{"scope_denied":"ACCESS-1"}',
                                     'FABRIC_EXECUTED_RISK_IDS_JSON': '["ACCESS-2"]', 'FABRIC_DISPATCH_STORAGE': 'configurable'}):
            self.assertEqual(dispatch.risk_ids(['scope_denied'], 'denied'), ['ACCESS-1'])
            self.assertEqual(dispatch.risk_ids([], 'executed'), ['ACCESS-2'])
            self.assertEqual(dispatch_storage_mode(), 'configurable')

    def test_invalid_dispatch_configuration_precedes_storage_or_delivery(self):
        for variable, value in (('FABRIC_DISPATCH_RISK_MAP_JSON', '{}'), ('FABRIC_EXECUTED_RISK_IDS_JSON', '[]'),
                                ('FABRIC_DISPATCH_RISK_MAP_JSON', '{"reason":["risk"]}'),
                                ('FABRIC_DISPATCH_STORAGE', 'cfg_outbox; DROP TABLE cfg_principals')):
            with self.subTest(variable=variable), patch.dict(os.environ, {variable: value}), \
                    patch.object(dispatch, 'PostgresFabric', side_effect=AssertionError('Must not touch storage')), \
                    patch.object(dispatch, 'DispatchStore', side_effect=AssertionError('Must not touch storage')):
                with self.assertRaises(ConfigurationError):
                    dispatch.once()

    def test_dispatch_uses_configurable_tables_and_durable_receipts(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        conn.executescript('CREATE TABLE cfg_principals(id TEXT,tenant TEXT); '
                           'CREATE TABLE cfg_outbox(id TEXT,kind TEXT,body TEXT,delivered INT);')
        conn.execute('INSERT INTO cfg_principals VALUES(?,?)', ('ops-bot', 'operations'))
        conn.execute('INSERT INTO cfg_outbox VALUES(?,?,?,0)', ('event-1', 'evidence', json.dumps({'actor': 'ops-bot', 'outcome': 'executed', 'workflow_id': 'ops-flow'})))
        conn.commit()
        store = SimpleNamespace(connect=lambda: contextlib.nullcontext(conn), tx=lambda: conn)
        ciso = MagicMock()
        ciso.evidence.return_value = {'id': 'simulated-evidence'}
        telemetry = SimpleNamespace(OUTBOX=MagicMock())
        bindings = {'ops-flow': {'reason_to_risk': {'scope_denied': 'OPS-2'}, 'executed_risk_ids': ['OPS-1']}}
        with patch.dict(os.environ, {'FABRIC_DISPATCH_STORAGE': 'configurable', 'FABRIC_WORKFLOW_RISK_BINDINGS_JSON': json.dumps(bindings)}), \
                patch.object(dispatch, 'DispatchStore', return_value=store), \
                patch.object(dispatch, 'PostgresFabric', side_effect=AssertionError('Must not create legacy schema')), \
                patch.object(dispatch, 'CISOAssistant', return_value=ciso), \
                patch.dict('sys.modules', {'fabric.enterprise.telemetry': telemetry}):
            self.assertEqual(dispatch.once(), 1)
            self.assertEqual(dispatch.once(), 0)
        self.assertEqual(ciso.evidence.call_count, 1)
        self.assertEqual(ciso.evidence.call_args.args[1]['risk_ids'], ['OPS-1'])
        self.assertEqual(conn.execute('SELECT count(*) FROM cfg_sink_receipts').fetchone()[0], 1)

    def test_configurable_approval_wait_does_not_create_incident_or_ticket(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        conn.executescript('CREATE TABLE cfg_principals(id TEXT,tenant TEXT); '
                           'CREATE TABLE cfg_outbox(id TEXT,kind TEXT,body TEXT,delivered INT);')
        source = {'actor': 'ops-bot', 'outcome': 'denied', 'reason': 'approval_required', 'workflow_id': 'ops-flow'}
        conn.execute('INSERT INTO cfg_outbox VALUES(?,?,?,1)', ('source', 'evidence', json.dumps(source)))
        conn.execute('INSERT INTO cfg_outbox VALUES(?,?,?,0)', ('waiting', 'incident', json.dumps({'event_id': 'source', 'reason': 'approval_required'})))
        conn.commit()
        store = SimpleNamespace(connect=lambda: contextlib.nullcontext(conn), tx=lambda: conn)
        ciso = MagicMock()
        ciso.evidence.return_value = {'id': 'simulated-evidence'}
        bindings = {'ops-flow': {'reason_to_risk': {'approval_required': 'OPS-2'}, 'executed_risk_ids': ['OPS-1']}}
        with patch.dict(os.environ, {'FABRIC_DISPATCH_STORAGE': 'configurable', 'FABRIC_WORKFLOW_RISK_BINDINGS_JSON': json.dumps(bindings)}), \
                patch.object(dispatch, 'DispatchStore', return_value=store), \
                patch.object(dispatch, 'CISOAssistant', return_value=ciso), \
                patch.object(dispatch, 'IRIS', side_effect=AssertionError('Approval waiting is not an incident')), \
                patch.object(dispatch, 'GLPI', side_effect=AssertionError('Approval waiting needs no ticket')), \
                patch.dict('sys.modules', {'fabric.enterprise.telemetry': SimpleNamespace(OUTBOX=MagicMock())}):
            self.assertEqual(dispatch.once(), 1)
        ciso.evidence.assert_called_once()

    def simulated_dispatch_store(self, rows):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        conn.executescript('CREATE TABLE cfg_principals(id TEXT,tenant TEXT); '
                           'CREATE TABLE cfg_outbox(id TEXT,kind TEXT,body TEXT,delivered INT);')
        conn.execute('INSERT INTO cfg_principals VALUES(?,?)', ('ops-bot', 'shared-tenant'))
        for event_id, kind, payload, delivered in rows:
            conn.execute('INSERT INTO cfg_outbox VALUES(?,?,?,?)', (event_id, kind, json.dumps(payload), delivered))
        conn.commit()
        return conn, SimpleNamespace(connect=lambda: contextlib.nullcontext(conn), tx=lambda: conn)

    def test_two_workflows_use_distinct_risks_and_incident_correlations(self):
        bindings = {
            'access': {'reason_to_risk': {'scope_denied': 'ACCESS-DENIED'}, 'executed_risk_ids': ['ACCESS-EXECUTED']},
            'expense': {'reason_to_risk': {'scope_denied': 'EXPENSE-DENIED'}, 'executed_risk_ids': ['EXPENSE-EXECUTED']},
        }
        rows = []
        for workflow_id in bindings:
            source = {'workflow_id': workflow_id, 'actor': 'ops-bot', 'outcome': 'denied', 'reason': 'scope_denied', 'time': 1000}
            rows.extend([
                (workflow_id + '-source', 'evidence', source, 1),
                (workflow_id + '-incident', 'incident', {'workflow_id': workflow_id, 'event_id': workflow_id + '-source', 'reason': 'scope_denied'}, 0),
                (workflow_id + '-executed', 'evidence', {**source, 'outcome': 'executed', 'reason': ''}, 0),
            ])
        conn, store = self.simulated_dispatch_store(rows)
        ciso, iris, glpi = MagicMock(), MagicMock(), MagicMock()
        ciso.evidence.return_value = iris.alert.return_value = glpi.remediation.return_value = {'id': 'simulated-receipt'}
        with patch.dict(os.environ, {'FABRIC_DISPATCH_STORAGE': 'configurable',
                                     'FABRIC_WORKFLOW_RISK_BINDINGS_JSON': json.dumps(bindings),
                                     'FABRIC_DISPATCH_RISK_MAP_JSON': '{}', 'FABRIC_EXECUTED_RISK_IDS_JSON': '[]'}), \
                patch.object(dispatch, 'DispatchStore', return_value=store), \
                patch.object(dispatch, 'CISOAssistant', return_value=ciso), \
                patch.object(dispatch, 'IRIS', return_value=iris), patch.object(dispatch, 'GLPI', return_value=glpi), \
                patch.dict('sys.modules', {'fabric.enterprise.telemetry': SimpleNamespace(OUTBOX=MagicMock())}):
            self.assertEqual(dispatch.once(), 4)
        linked = {call.args[0]: call.args[1]['risk_ids'] for call in ciso.evidence.call_args_list}
        self.assertEqual(linked, {'access-incident': ['ACCESS-DENIED'], 'access-executed': ['ACCESS-EXECUTED'],
                                 'expense-incident': ['EXPENSE-DENIED'], 'expense-executed': ['EXPENSE-EXECUTED']})
        self.assertEqual(iris.alert.call_count, 2)
        self.assertEqual(glpi.remediation.call_count, 2)
        self.assertNotEqual(iris.alert.call_args_list[0].args[0], iris.alert.call_args_list[1].args[0])
        self.assertEqual(conn.execute('SELECT count(*) FROM cfg_outbox WHERE delivered=0').fetchone()[0], 0)

    def test_missing_workflow_risk_binding_retains_event_without_delivery(self):
        for payload in ({'workflow_id': 'unbound', 'outcome': 'executed'}, {'outcome': 'executed'}):
            with self.subTest(payload=payload):
                conn, store = self.simulated_dispatch_store([('event', 'evidence', payload, 0)])
                with patch.dict(os.environ, {'FABRIC_DISPATCH_STORAGE': 'configurable'}), \
                        patch.object(dispatch, 'DispatchStore', return_value=store), \
                        patch.object(dispatch, 'CISOAssistant', side_effect=AssertionError('Unbound event must not be delivered')), \
                        patch.dict('sys.modules', {'fabric.enterprise.telemetry': SimpleNamespace(OUTBOX=MagicMock())}):
                    with self.assertRaises(ConfigurationError):
                        dispatch.once()
                self.assertEqual(conn.execute('SELECT delivered FROM cfg_outbox').fetchone()[0], 0)
                self.assertEqual(conn.execute('SELECT count(*) FROM cfg_sink_receipts').fetchone()[0], 0)

    def test_platform_provisioning_evidence_has_no_invented_risk_links(self):
        conn, store = self.simulated_dispatch_store([
            ('provision', 'evidence', {'outcome': 'principal_provisioned', 'principal_id': 'ops-bot', 'risk_ids': ['R01']}, 0)])
        ciso = MagicMock()
        ciso.evidence.return_value = {'id': 'simulated-evidence'}
        with patch.dict(os.environ, {'FABRIC_DISPATCH_STORAGE': 'configurable'}), \
                patch.object(dispatch, 'DispatchStore', return_value=store), \
                patch.object(dispatch, 'CISOAssistant', return_value=ciso), \
                patch.object(dispatch, 'IRIS', side_effect=AssertionError('Provisioning is not an incident')), \
                patch.object(dispatch, 'GLPI', side_effect=AssertionError('Provisioning needs no ticket')), \
                patch.dict('sys.modules', {'fabric.enterprise.telemetry': SimpleNamespace(OUTBOX=MagicMock())}):
            self.assertEqual(dispatch.once(), 1)
        self.assertEqual(ciso.evidence.call_args.args[1]['risk_ids'], [])

    def test_invalid_workflow_risk_bindings_fail_closed(self):
        invalid = ('{}', '[]', '{"access":{}}',
                   '{"access":{"reason_to_risk":{},"executed_risk_ids":["A"]}}',
                   '{"access":{"reason_to_risk":{"scope_denied":"A"},"executed_risk_ids":[]}}',
                   '{"access":{"reason_to_risk":{"scope_denied":["A"]},"executed_risk_ids":["B"]}}')
        for raw in invalid:
            with self.subTest(raw=raw), patch.dict(os.environ, {'FABRIC_WORKFLOW_RISK_BINDINGS_JSON': raw}):
                with self.assertRaises(ConfigurationError):
                    workflow_risk_bindings()

    def test_evaluation_supplied_data_and_requirements_cli(self):
        data = {**evaluate.synthetic_fixture(), 'dataset': 'supplied-access-classifier'}
        metrics = {'fairness_difference': 0, 'accuracy': 0.9, 'selection_rate': 0.5, 'accuracy_difference': 0}
        registry = MagicMock()
        registry.publish_evaluation.return_value = {'version': '2'}
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / 'data.json'
            gate_path = Path(directory) / 'gates.json'
            data_path.write_text(json.dumps(data), encoding='utf-8')
            gate_path.write_text('{"accuracy":{"min":0.8}}', encoding='utf-8')
            with patch.object(evaluate, 'compute_metrics', return_value=(metrics, {})) as compute, \
                    patch.object(evaluate, 'MLflowRegistry', return_value=registry), contextlib.redirect_stdout(io.StringIO()):
                result = evaluate.main(['--data', str(data_path), '--metric-requirements', str(gate_path)])
        compute.assert_called_once_with(data)
        self.assertEqual(result['dataset_origin'], 'operator_supplied')
        artifact = registry.publish_evaluation.call_args.args[1]
        self.assertEqual(artifact['metric_requirements'], {'accuracy': {'min': 0.8}})
        self.assertEqual(len(artifact['dataset_sha256']), 64)
        self.assertIn('candidate only', result['release'])

    def test_default_evaluation_is_explicitly_synthetic(self):
        registry = MagicMock()
        with patch.object(evaluate, 'compute_metrics', return_value=({'fairness_difference': 0}, {})), \
                patch.object(evaluate, 'MLflowRegistry', return_value=registry):
            result = evaluate.evaluate()
        self.assertEqual(result['dataset'], 'synthetic-eight-record-fixture')
        self.assertEqual(result['dataset_origin'], 'synthetic_fixture')
        self.assertIn('not fair lending validity', registry.publish_evaluation.call_args.args[1]['limitations'])

    def test_invalid_dataset_or_unsupported_requirement_prevents_evaluation(self):
        data = evaluate.synthetic_fixture()
        invalid = [{**data, 'y_pred': [1]}, {**data, 'y_true': [True] * 8},
                   {**data, 'sensitive_features': ['a'] * 8}, {**data, 'extra': 'unknown'}]
        with patch.object(evaluate, 'compute_metrics', side_effect=AssertionError('Must not compute')):
            for dataset in invalid:
                with self.subTest(dataset=dataset), self.assertRaises(ConfigurationError):
                    evaluate.evaluate(dataset)
            with self.assertRaises(ConfigurationError):
                evaluate.evaluate(data, {'latency': {'max': 1}})

    def test_failed_evaluation_requirement_does_not_publish(self):
        with patch.object(evaluate, 'compute_metrics', return_value=({'accuracy': 0.5}, {})), \
                patch.object(evaluate, 'MLflowRegistry', side_effect=AssertionError('Must not publish')):
            with self.assertRaises(ConfigurationError):
                evaluate.evaluate(evaluate.synthetic_fixture(), {'accuracy': {'min': 0.8}})


if __name__ == '__main__':
    unittest.main()
