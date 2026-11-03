"""Real loopback HTTP tests; model inference and model discovery are simulated."""
import copy
import json
from pathlib import Path
import socket
import threading
import time
import unittest
from unittest.mock import patch

import httpx

from fabric.designer import DesignerError, WorkflowDesigner
from fabric.studio import MAX_BODY_BYTES, MAX_JOBS, make_server


ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'An assistant drafts a library notice. A librarian reviews the notice before publication.'


def model_draft():
    stated = {'source_state': 'stated', 'evidence_ids': ['ev-description']}
    draft = {key: [] for key in ('assumptions', 'data', 'tools', 'decisions', 'edges',
                                'requirements', 'existing_controls', 'gaps')}
    draft.update({
        'workflow': {'title': 'Library notices', 'summary': 'Draft and review a notice.'},
        'evidence': [{'id': 'ev-description', 'quote': SOURCE}],
        'facts': [{'id': 'fact-process', 'evidence_ids': ['ev-description']}],
        'actors': [{'id': 'actor-assistant', 'label': 'Assistant', 'kind': 'ai', **stated},
                   {'id': 'actor-librarian', 'label': 'Librarian', 'kind': 'human', **stated}],
        'steps': [{'id': 'step-draft', 'label': 'Draft notice', 'description': 'Draft a notice.',
                   'actor_ids': ['actor-assistant'], 'input_data_ids': [], 'output_data_ids': [], 'tool_ids': [], **stated},
                  {'id': 'step-review', 'label': 'Review notice', 'description': 'Review before publication.',
                   'actor_ids': ['actor-librarian'], 'input_data_ids': [], 'output_data_ids': [], 'tool_ids': [], **stated}],
        'risks': [{'id': 'risk-errors', 'title': 'Incorrect notice', 'scenario': 'A draft misstates library hours.',
                   'impact': 'Readers visit at the wrong time.', 'step_ids': ['step-draft'], 'data_ids': [],
                   'evidence_ids': ['ev-description'], 'uncertainty': 'Error rate unknown.', 'proposed_priority': 'needs_assessment'}],
        'controls': [{'id': 'ctrl-review', 'family': 'human_approval', 'recommendation': 'Require review before publication.',
                      'enforcement_point': 'Publication', 'risk_ids': ['risk-errors'], 'step_ids': ['step-review'],
                      'owner_actor_ids': ['actor-librarian'], 'validation': 'Submit an unreviewed notice; expect denial and no publication.'}],
        'questions': [{'id': 'question-criteria', 'question': 'Which review criteria apply?', 'related_ids': ['step-review'], 'blocking': True}],
        'human_authority': {'accountable_actor_ids': ['actor-librarian'], 'reviewer_actor_ids': ['actor-librarian'],
                            'approval_points': [], 'escalation': 'Hold the notice and ask the librarian.'},
    })
    return draft


class StudioHTTPTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.model_calls = []
        self.release = threading.Event()
        self.release.set()
        self.failure = None
        self.discovery = lambda request: httpx.Response(200, json={'models': [
            {'name': 'test-model', 'size': 123, 'modified_at': '2026-11-03'}]})

        def factory(endpoint, model, **options):
            self.calls.append((endpoint, model, options))
            self.release.wait(4)
            if self.failure:
                raise self.failure
            def respond(request):
                self.model_calls.append(request)
                return httpx.Response(200, json={'model': model, 'done': True,
                    'message': {'role': 'assistant', 'content': json.dumps(model_draft())}})
            return WorkflowDesigner(endpoint, model, transport=httpx.MockTransport(respond), **options)

        definitions = [json.loads((ROOT / 'workflows' / (name + '.json')).read_text())
                       for name in ('synthetic-credit', 'it-access')]
        self.server = make_server(0, model='test-model', designer_factory=factory,
            model_transport=httpx.MockTransport(lambda request: self.discovery(request)),
            catalog=(definitions, [{'id': 'library-notice', 'title': 'Library notices', 'description': SOURCE}]))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.client = httpx.Client(base_url=self.url, trust_env=False, timeout=3)
        self.token = self.client.get('/api/bootstrap').json()['session_token']
        self.headers = {'X-Fabric-Session': self.token}

    def tearDown(self):
        self.release.set()
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)

    def get(self, path, **kwargs):
        return self.client.get(path, headers=self.headers, **kwargs)

    def post(self, path, value):
        return self.client.post(path, json=value, headers=self.headers)

    def wait_job(self, job_id):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            response = self.get('/api/jobs/' + job_id)
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            if result['status'] in ('succeeded', 'failed'):
                return result
            time.sleep(0.01)
        self.fail('job did not finish')

    def raw(self, request):
        with socket.create_connection(('127.0.0.1', self.server.server_port), timeout=3) as connection:
            connection.sendall(request)
            chunks = []
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        data = b''.join(chunks)
        return int(data.split(b' ', 2)[1]), data

    def test_bootstrap_catalog_is_data_and_token_is_per_server(self):
        data = self.get('/api/bootstrap').json()
        self.assertEqual(len(data['components']), 18)
        self.assertEqual(len(data['inputs']), 7)
        self.assertEqual(len(data['outputs']), 12)
        self.assertEqual({item['workflow_id'] for item in data['workflows']}, {'synthetic-credit', 'it-access'})
        self.assertEqual(data['model']['endpoint'], 'http://127.0.0.1:11434')
        self.assertGreaterEqual(len(data['session_token']), 40)
        other = make_server(0, catalog=(data['workflows'], []))
        try:
            self.assertNotEqual(other.studio.session_token, self.token)
        finally:
            other.server_close()
        self.assertEqual(self.calls, [])

    def test_session_required_for_reads_and_writes(self):
        for method, path in [('GET', '/api/models'), ('GET', '/api/jobs/' + '0' * 32),
                             ('POST', '/api/design'), ('POST', '/api/package'), ('POST', '/api/demo')]:
            for token in (None, 'incorrect'):
                with self.subTest(method=method, path=path, token=token):
                    headers = {} if token is None else {'X-Fabric-Session': token}
                    self.assertEqual(self.client.request(method, path, headers=headers).status_code, 403)

    def test_exact_host_origin_and_fetch_metadata(self):
        for headers in ({'Host': 'evil.example'}, {'Host': 'localhost'},
                        {'Host': f'127.0.0.1:{self.server.server_port + 1}'},
                        {'Origin': 'https://evil.example'}, {'Origin': 'null'},
                        {'Origin': f'http://localhost:{self.server.server_port}'},
                        {'Sec-Fetch-Site': 'cross-site'}, {'Sec-Fetch-Site': 'same-site'}):
            with self.subTest(headers=headers):
                self.assertEqual(self.client.get('/api/bootstrap', headers=headers).status_code, 403)
        good = self.client.get('/api/bootstrap', headers={'Origin': self.url, 'Sec-Fetch-Site': 'same-origin'})
        self.assertEqual(good.status_code, 200)
        localhost = f'localhost:{self.server.server_port}'
        self.assertEqual(self.client.get('/api/bootstrap', headers={'Host': localhost, 'Origin': 'http://' + localhost}).status_code, 200)

    def test_frame_csp_cache_and_static_allowlist(self):
        # Root owns these resources; the test verifies the installed allowlist.
        for path in ('/', '/index.html', '/app.js', '/styles.css', '/packages.js'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn("frame-ancestors 'none'", response.headers['content-security-policy'])
            self.assertNotIn('unsafe-inline', response.headers['content-security-policy'])
            self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
            self.assertEqual(response.headers['cache-control'], 'no-store')
            self.assertEqual(response.headers['x-frame-options'], 'DENY')
            self.assertNotIn('access-control-allow-origin', response.headers)
        for path in ('/../pyproject.toml', '/%2e%2e/pyproject.toml', '/web/data/synthetic-credit.json',
                     '/api/execute', '/api/approve', '/index.html?file=../pyproject.toml'):
            status, _ = self.raw(f'GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\nX-Fabric-Session: {self.token}\r\n\r\n'.encode())
            self.assertEqual(status, 404, path)

    def test_strict_json_and_content_type(self):
        invalid = [b'{"workflows":[],"workflows":[]}', b'{"workflows":NaN}',
                   b'{"workflows":Infinity}', b'{"workflows":1e9999}',
                   b'{"workflows":"\\ud800"}', b'\xff', b'[' * 2000]
        for raw in invalid:
            with self.subTest(raw=raw[:40]):
                response = self.client.post('/api/package', content=raw,
                    headers={**self.headers, 'Content-Type': 'application/json'})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['error'], 'invalid_json')
        for media in ('text/plain', 'application/x-www-form-urlencoded', 'application/jsonp'):
            response = self.client.post('/api/design', content=b'{}', headers={**self.headers, 'Content-Type': media})
            self.assertEqual(response.status_code, 415)

    def test_ambiguous_headers_and_request_size_fail_closed(self):
        base = f'POST /api/package HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\nX-Fabric-Session: {self.token}\r\nContent-Type: application/json\r\n'
        cases = [(f'Content-Length: {MAX_BODY_BYTES + 1}\r\n', 413),
                 ('Content-Length: 2\r\nContent-Length: 2\r\n', 400),
                 ('Transfer-Encoding: chunked\r\nContent-Length: 2\r\n', 400),
                 ('Content-Length: -1\r\n', 400),
                 ('Content-Length: 2\r\nHost: evil.example\r\n', 400),
                 ('Content-Length: 2\r\nOrigin: null\r\nOrigin: null\r\n', 400),
                 (f'Content-Length: 2\r\nX-Fabric-Session: {self.token}\r\n', 400)]
        for extra, expected in cases:
            with self.subTest(extra=extra):
                status, _ = self.raw((base + extra + '\r\n{}').encode())
                self.assertEqual(status, expected)

    def test_incomplete_body_times_out_without_hanging(self):
        with patch('fabric.studio.BODY_TIMEOUT', 0.15):
            status, raw = self.raw((f'POST /api/package HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\n'
                                   f'X-Fabric-Session: {self.token}\r\nContent-Type: application/json\r\nContent-Length: 20\r\n\r\n{{').encode())
        self.assertEqual(status, 408)
        self.assertIn(b'request_timeout', raw)

    def test_methods_cannot_create_other_operations(self):
        for method in ('OPTIONS', 'PUT', 'DELETE', 'PATCH', 'HEAD'):
            response = self.client.request(method, '/api/bootstrap')
            self.assertEqual(response.status_code, 405)
        self.assertEqual(self.post('/api/execute', {}).status_code, 404)

    def test_package_validates_and_exports_disabled_data_without_execution(self):
        definitions = self.get('/api/bootstrap').json()['workflows']
        with patch('fabric.studio.demo') as demonstration, patch('fabric.runtime.ConfigurableFabric.execute') as execute:
            response = self.post('/api/package', {'workflows': definitions})
            self.assertEqual(response.status_code, 200, response.text)
            demonstration.assert_not_called()
            execute.assert_not_called()
        data = response.json()
        self.assertEqual(data['package']['deployment_status'], 'unapproved')
        self.assertFalse(data['package']['secrets_included'])
        self.assertTrue(all(item['enabled'] is False for item in data['package']['opa_data']['fabric_workflows'].values()))
        self.assertIn('# Governance design', data['report'])
        self.assertEqual(self.calls, [])

    def test_configuration_cannot_add_endpoints_code_or_unknown_fields(self):
        definition = self.get('/api/bootstrap').json()['workflows'][0]
        invalid = [[], [definition] * 2, [definition] * 17,
                   [{**definition, 'endpoint': 'http://evil.example'}],
                   [{**definition, 'schema_version': True}]]
        modified = copy.deepcopy(definition)
        next(iter(modified['operations'].values()))['adapter'] = 'http://evil.example'
        invalid.append([modified])
        for definitions in invalid:
            self.assertEqual(self.post('/api/package', {'workflows': definitions}).status_code, 400)
        self.assertEqual(self.post('/api/package', {'workflows': [definition], 'deploy': True}).status_code, 400)

    def test_json_escapes_html_without_changing_original_data(self):
        definitions = self.get('/api/bootstrap').json()['workflows']
        text = '</script><img src=x onerror=alert(1)> & other text'
        definitions[0]['description'] = text
        response = self.post('/api/package', {'workflows': definitions})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('<', response.text)
        self.assertIn('\\u003c', response.text)
        self.assertEqual(response.json()['package']['workflow_definitions'][0]['description'], text)

    def test_demo_requires_explicit_known_ids_and_uses_fresh_synthetic_state(self):
        for _ in range(2):
            response = self.post('/api/demo', {'workflow_ids': ['synthetic-credit', 'it-access']})
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual(data['effects'], 2)
            self.assertTrue(data['audit_chain_valid'])
            self.assertIn('no external systems', data['scope'])
            for journey in data['workflows']:
                self.assertEqual(journey['before_approval']['reason'], 'approval_required')
                self.assertEqual(journey['after_approval']['status'], 'executed')
                self.assertTrue(journey['retry_returns_same_receipt'])
        for ids in ([], ['unknown'], ['synthetic-credit'] * 2, [{}]):
            self.assertEqual(self.post('/api/demo', {'workflow_ids': ids}).status_code, 400)
        self.assertEqual(self.post('/api/demo', {'workflow_ids': ['synthetic-credit'], 'adapters': {}}).status_code, 400)
        self.assertEqual(self.calls, [])

    def test_design_job_returns_review_artifact_and_markdown_with_real_validation(self):
        with patch('fabric.runtime.ConfigurableFabric.execute') as execute:
            response = self.post('/api/design', {'description': SOURCE, 'thinking': True})
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(response.json()['status'], 'queued')
            result = self.wait_job(response.json()['id'])
            execute.assert_not_called()
        self.assertEqual(result['status'], 'succeeded', result)
        self.assertFalse(result['result']['execution']['allowed'])
        self.assertEqual(result['result']['status'], 'draft_requires_review')
        self.assertIn('# Library notices', result['report'])
        self.assertGreaterEqual(result['elapsed_seconds'], 0)
        self.assertNotIn('description', self.server.studio.jobs[result['id']])
        self.assertEqual(self.calls[0], ('http://127.0.0.1:11434', 'test-model', {'timeout': 600, 'thinking': True}))

    def test_single_active_job_and_safe_failure(self):
        self.release.clear()
        self.failure = RuntimeError('secret prose and raw provider response')
        first = self.post('/api/design', {'description': SOURCE, 'model': 'selected-model'}).json()
        self.assertEqual(self.get('/api/jobs/' + first['id']).json()['status'], 'running')
        self.assertEqual(self.post('/api/design', {'description': SOURCE}).status_code, 409)
        self.release.set()
        result = self.wait_job(first['id'])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error'], 'design_failed')
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('result', result)
        elapsed = result['elapsed_seconds']
        time.sleep(0.02)
        self.assertEqual(self.get('/api/jobs/' + first['id']).json()['elapsed_seconds'], elapsed)

    def test_designer_failure_uses_safe_code_without_provider_detail(self):
        self.failure = DesignerError('model_design_validation_failed', attempts=[{'private': SOURCE}])
        response = self.post('/api/design', {'description': SOURCE})
        result = self.wait_job(response.json()['id'])
        self.assertEqual(result['error'], 'model_design_validation_failed')
        self.assertNotIn(SOURCE, json.dumps(result))
        self.assertNotIn('attempts', result)

    def test_invalid_design_fields_do_not_reach_model(self):
        bodies = [{'description': ''}, {'description': 'x' * 12001}, {'description': '\x00'},
                  {'description': SOURCE, 'thinking': 'true'}, {'description': SOURCE, 'model': ''},
                  {'description': SOURCE, 'endpoint': 'http://evil.example'},
                  {'description': SOURCE, 'output': '/tmp/private'}, {'description': SOURCE, 'model': 'a b'}]
        for body in bodies:
            self.assertEqual(self.post('/api/design', body).status_code, 400)
        self.assertEqual(self.calls, [])

    def test_completed_jobs_are_bounded_and_oldest_is_evicted(self):
        self.failure = DesignerError('model_transport_unavailable')
        ids = []
        for _ in range(MAX_JOBS + 2):
            response = self.post('/api/design', {'description': SOURCE})
            self.assertEqual(response.status_code, 202)
            ids.append(response.json()['id'])
            self.wait_job(ids[-1])
        self.assertEqual(len(self.server.studio.jobs), MAX_JOBS)
        self.assertEqual(self.get('/api/jobs/' + ids[0]).status_code, 404)
        self.assertEqual(self.get('/api/jobs/' + ids[-1]).status_code, 200)

    def test_model_discovery_is_bounded_and_does_not_follow_redirects(self):
        response = self.get('/api/models')
        self.assertTrue(response.json()['reachable'])
        self.assertEqual(response.json()['models'][0]['name'], 'test-model')
        seen = []
        def redirect(request):
            seen.append(str(request.url))
            return httpx.Response(302, headers={'location': 'http://evil.example/steal'})
        self.discovery = redirect
        response = self.get('/api/models')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['reachable'])
        self.assertEqual(seen, ['http://127.0.0.1:11434/api/tags'])
        self.discovery = lambda request: httpx.Response(200, content=b'x' * 524289)
        self.assertFalse(self.get('/api/models').json()['reachable'])
        self.discovery = lambda request: httpx.Response(200, json={'models': [{'name': 'bad model'}]})
        self.assertFalse(self.get('/api/models').json()['reachable'])

    def test_model_connection_failure_has_safe_success_status(self):
        def fail(request):
            raise httpx.ConnectError('secret provider data', request=request)
        self.discovery = fail
        response = self.get('/api/models')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['reachable'])
        self.assertNotIn('secret', response.text)


if __name__ == '__main__':
    unittest.main()
