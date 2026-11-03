"""Simulated native authority/Temporal contracts, not live deployment evidence."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fabric.configuration import WorkflowRegistry
from fabric.enterprise.configurable import NativeAuthorities
from fabric.enterprise.clients import DependencyFailure


class NativeBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(__file__).resolve().parents[2]
        self.registry = WorkflowRegistry.from_paths([root / 'workflows/it-access.json'])
        self.definition = self.registry.get('it-access')
        self.binding = {'required_capabilities': ['opa', 'relationships'],
                        'opa_decision_url': 'https://opa.invalid/v1/data/fabric_configurable/decision',
                        'fga_user_type': 'employee', 'fga_object_type': 'application', 'fga_relation': 'requester'}
        self.ctx = {'action': {'workflow_id': 'it-access'}, 'config_digest': self.definition.digest,
                    'principal': {'id': 'agent', 'tenant': 'org'}, 'resource': {'id': 'record', 'tenant': 'org'}}

    def tearDown(self):
        self.tmp.cleanup()

    def authority(self, binding=None, workflows=None):
        path = Path(self.tmp.name) / 'bindings.json'
        path.write_text(json.dumps({'schema_version': '1.0', 'workflows':
            workflows if workflows is not None else {'it-access': binding or self.binding}}), encoding='utf-8')
        return NativeAuthorities(self.registry, path)

    def test_no_unbound_workflow_or_unknown_capability_fallback(self):
        with self.assertRaises(ValueError):
            self.authority(workflows={})
        with self.assertRaises(ValueError):
            self.authority({**self.binding, 'required_capabilities': ['opa', 'relationships', 'invented']})
        with self.assertRaises(ValueError):
            self.authority({**self.binding, 'required_capabilities': ['opa']})

    def test_resource_relationship_is_workflow_and_tenant_scoped(self):
        authority = self.authority()
        fga = MagicMock()
        fga.check.return_value = True
        with patch('fabric.enterprise.configurable.OpenFGA', return_value=fga):
            self.assertTrue(authority.authorize_read(self.ctx['principal'], self.ctx['resource'], self.definition))
        fga.check.assert_called_once_with('agent', authority.resource_key('it-access', 'org', 'record'), user_type='employee', object_type='application', relation='requester')
        fga.close.assert_called_once()

    def test_scope_encoding_cannot_collide_and_required_gates_cannot_use_legacy_defaults(self):
        self.assertNotEqual(NativeAuthorities.resource_key('access', 'org/x', 'y'),
                            NativeAuthorities.resource_key('access', 'org', 'x/y'))
        for capability in ('metadata', 'model', 'inventory'):
            with self.assertRaises(ValueError):
                self.authority({**self.binding, 'required_capabilities': ['opa', 'relationships', capability]})

    def test_changed_opa_config_binding_rejects_before_relationship_call(self):
        authority = self.authority()
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value.json.return_value = {'result': {'allow': True, 'config_digest': 'different'}}
        with patch('fabric.enterprise.configurable.httpx.Client', return_value=client), patch('fabric.enterprise.configurable.OpenFGA') as fga:
            with self.assertRaises(DependencyFailure):
                authority.decide(self.ctx)
            fga.assert_not_called()

    def test_explicit_native_allow_cannot_ignore_relationship_denial(self):
        authority = self.authority()
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value.json.return_value = {'result': {'allow': True, 'config_digest': self.definition.digest}}
        fga = MagicMock()
        fga.check.return_value = False
        with patch('fabric.enterprise.configurable.httpx.Client', return_value=client), patch('fabric.enterprise.configurable.OpenFGA', return_value=fga):
            self.assertEqual(authority.decide(self.ctx), {'allow': False})


class GenericWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_hard_denial_does_not_wait_or_retry_business_intent(self):
        from fabric.enterprise import configurable_workflows as module
        instance = module.GovernedOperation()
        activity = AsyncMock(return_value={'status': 'denied', 'reason': 'external_policy_denied'})
        wait = AsyncMock()
        with patch.object(module.workflow, 'execute_activity', activity), patch.object(module.workflow, 'wait_condition', wait):
            result = await instance.run({'action': {'workflow_id': 'it-access'}, 'actor': 'agent', 'approval_timeout_seconds': 30})
        self.assertEqual(result['status'], 'denied')
        self.assertEqual(activity.await_count, 1)
        wait.assert_not_awaited()

    async def test_approval_wait_submits_same_action_with_reference(self):
        from fabric.enterprise import configurable_workflows as module
        instance = module.GovernedOperation()
        activity = AsyncMock(side_effect=[{'status': 'denied', 'reason': 'approval_required'}, {'status': 'executed'}])
        async def signal(*args, **kwargs):
            instance.approval('stored-approval')
        action = {'workflow_id': 'it-access', 'operation': 'grant_access'}
        with patch.object(module.workflow, 'execute_activity', activity), patch.object(module.workflow, 'wait_condition', side_effect=signal):
            result = await instance.run({'action': action, 'actor': 'agent', 'approval_timeout_seconds': 30})
        self.assertEqual(result['status'], 'executed')
        self.assertEqual(activity.await_args_list[1].args[1], {'action': action, 'actor': 'agent', 'approval_id': 'stored-approval'})


class ConfigurableToolkitTests(unittest.TestCase):
    def test_real_toolkit_wraps_both_profiles_without_overriding_gateway(self):
        from fabric.adapters import builtin_adapters
        from fabric.runtime import ConfigurableFabric
        from fabric.microsoft_agt import install_configurable
        from fabric.core import Rejected
        root = Path(__file__).resolve().parents[2]
        registry = WorkflowRegistry.from_paths([root / 'workflows/synthetic-credit.json', root / 'workflows/it-access.json'])
        with tempfile.TemporaryDirectory() as folder:
            fabric = ConfigurableFabric(Path(folder) / 'test.db', registry, adapters=builtin_adapters())
            fabric.provision_demo()
            install_configurable(fabric)
            credit = {'workflow_id': 'synthetic-credit', 'operation': 'commit_credit', 'resource_id': 'case-a',
                      'parameters': {'amount_pence': 1000, 'reason': 'test'}, 'idempotency_key': 'credit'}
            access = {'workflow_id': 'it-access', 'operation': 'grant_access', 'resource_id': 'employee-a',
                      'parameters': {'permission': 'read', 'duration_hours': 1, 'justification': 'test'}, 'idempotency_key': 'access'}
            self.assertEqual(fabric.execute('agent-a', credit)['status'], 'executed')
            self.assertEqual(fabric.execute('agent-a', access)['status'], 'executed')
            cross = {**credit, 'resource_id': 'case-b', 'idempotency_key': 'other'}
            self.assertEqual(fabric.execute('agent-a', cross)['status'], 'denied')
            with self.assertRaises(Rejected):
                fabric.execute('agent-a', {**credit, 'operation': 'shell'})
            def rejected(connection):
                raise Rejected('task_expired')
            with self.assertRaises(Rejected):
                fabric.execute('agent-a', credit, precondition=rejected)
