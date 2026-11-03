"""Loopback-only browser workbench for review drafts and synthetic demonstrations.

The operator chooses the model endpoint. Browser input cannot select network
targets, files, adapters, credentials or deployment actions. Private descriptions
and completed jobs remain in bounded process memory, never in server files.
"""

import argparse
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
import json
import math
import re
import secrets
import socket
import threading
import time
import webbrowser

import httpx

from .configuration import ConfigurationError, WorkflowRegistry
from .design import implementation_package, render_report
from .designer import DesignerError, MAX_DESCRIPTION_CHARS, WorkflowDesigner, render_design_report
from .framework import COMPONENTS, INPUTS, OUTPUTS
from .workflow_cli import demo


MAX_BODY_BYTES = 262144
MAX_MODEL_BYTES = 524288
MAX_JOBS = 8
BODY_TIMEOUT = 5
DESIGN_TIMEOUT = 600
STATIC_FILES = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/index.html': ('index.html', 'text/html; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
    '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
    '/packages.js': ('packages.js', 'text/javascript; charset=utf-8'),
}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; "
       "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
       "frame-ancestors 'none'; form-action 'none'; object-src 'none'")
SAFE_DESIGN_ERRORS = frozenset({
    'design_timeout', 'model_transport_unavailable', 'model_response_too_large',
    'invalid_model_response_length', 'model_design_validation_failed',
})


class RequestError(ValueError):
    def __init__(self, code, status=400):
        self.code, self.status = code, status
        super().__init__(code)


def strict_json(raw):
    """Decode only finite, unambiguous UTF-8 JSON with encodable strings."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result

    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('nonfinite number')
        return result

    def constant(_):
        raise ValueError('nonfinite number')

    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_float=number, parse_constant=constant)
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise RequestError('invalid_json') from exc


def shape(value, required, optional=()):
    if type(value) is not dict or not set(required) <= set(value) <= set(required) | set(optional):
        raise RequestError('invalid_fields')


def packaged_catalog():
    root = resources.files('fabric').joinpath('web', 'data')
    workflows = [strict_json(root.joinpath(name + '.json').read_bytes())
                 for name in ('synthetic-credit', 'it-access')]
    examples = [{'id': name, 'title': title,
                 'description': root.joinpath(name + '.txt').read_text(encoding='utf-8')}
                for name, title in (('vendor-onboarding', 'Vendor onboarding'),
                                    ('museum-loan', 'Museum loan requests'))]
    return workflows, examples


class Studio:
    """Trusted dependencies and bounded jobs, independent of HTTP plumbing."""
    def __init__(self, *, ollama_url='http://127.0.0.1:11434', model=None,
                 designer_factory=WorkflowDesigner, model_transport=None, catalog=None):
        # Reuse the designer's operator configuration validation without I/O.
        validated = WorkflowDesigner(ollama_url, model if model is not None else 'model',
                                     timeout=DESIGN_TIMEOUT)
        self.endpoint, self.default_model = validated.ollama_url, model
        self.designer_factory, self.model_transport = designer_factory, model_transport
        workflows, self.examples = packaged_catalog() if catalog is None else catalog
        self.registry = WorkflowRegistry(workflows)
        if set(self.registry.workflows) != {'synthetic-credit', 'it-access'}:
            raise ValueError('Studio requires the two bundled synthetic workflows')
        self.session_token = secrets.token_urlsafe(32)
        self.jobs = OrderedDict()
        self.lock = threading.Lock()
        self.active = None

    def bootstrap(self):
        return {'session_token': self.session_token,
                'model': {'endpoint': self.endpoint, 'default_model': self.default_model},
                'examples': self.examples,
                'workflows': [item.to_dict() for item in self.registry.workflows.values()],
                'components': COMPONENTS, 'inputs': INPUTS, 'outputs': OUTPUTS}

    def models(self):
        """Bounded, nonredirecting read from the operator's fixed endpoint."""
        failure = {'reachable': False, 'models': [], 'default_model': self.default_model,
                   'error': 'model_catalog_unavailable'}
        try:
            deadline = time.monotonic() + 6
            with httpx.Client(transport=self.model_transport, trust_env=False,
                              follow_redirects=False, timeout=4) as client:
                with client.stream('GET', self.endpoint + '/api/tags') as response:
                    if response.status_code != 200:
                        return failure
                    declared = response.headers.get('content-length')
                    if declared is not None and not 0 <= int(declared) <= MAX_MODEL_BYTES:
                        return failure
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_MODEL_BYTES or time.monotonic() > deadline:
                            return failure
                        chunks.append(chunk)
            data = strict_json(b''.join(chunks))
            if type(data) is not dict or type(data.get('models')) is not list or len(data['models']) > 100:
                return failure
            models = []
            for item in data['models']:
                if type(item) is not dict:
                    return failure
                name, size = item.get('name'), item.get('size')
                modified = item.get('modified_at')
                if (type(name) is not str or not 1 <= len(name) <= 200 or
                        any(ord(char) < 33 for char in name) or
                        (size is not None and (type(size) is not int or not 0 <= size <= 2**63)) or
                        (modified is not None and (type(modified) is not str or len(modified) > 100))):
                    return failure
                models.append({'name': name, 'size': size, 'modified_at': modified})
            return {'reachable': True, 'models': models, 'default_model': self.default_model}
        except (httpx.HTTPError, ValueError, UnicodeError, OverflowError):
            return failure

    def start_design(self, body):
        shape(body, ('description',), ('model', 'thinking'))
        description = body['description']
        model = body.get('model', self.default_model)
        thinking = body.get('thinking', False)
        if (type(description) is not str or not 1 <= len(description) <= MAX_DESCRIPTION_CHARS or
                not description.strip() or any(ord(char) < 32 and char not in '\n\r\t' for char in description)):
            raise RequestError('invalid_description')
        if type(model) is not str or not 1 <= len(model) <= 200 or any(ord(char) < 33 for char in model):
            raise RequestError('invalid_model')
        if type(thinking) is not bool:
            raise RequestError('invalid_thinking')
        with self.lock:
            if self.active is not None:
                raise RequestError('design_already_running', 409)
            while len(self.jobs) >= MAX_JOBS:
                self.jobs.popitem(last=False)
            job_id = secrets.token_hex(16)
            self.jobs[job_id] = {'id': job_id, 'status': 'queued', '_started': time.monotonic()}
            self.active = job_id
        worker = threading.Thread(target=self._design, args=(job_id, description, model, thinking), daemon=True)
        try:
            worker.start()
        except RuntimeError:
            with self.lock:
                self.jobs[job_id].update(status='failed', error='design_failed', _finished=time.monotonic())
                self.active = None
            raise RequestError('design_failed', 503)
        return {'id': job_id, 'status': 'queued'}

    def _design(self, job_id, description, model, thinking):
        with self.lock:
            self.jobs[job_id]['status'] = 'running'
        try:
            designer = self.designer_factory(self.endpoint, model, timeout=DESIGN_TIMEOUT, thinking=thinking)
            result = designer.design(description)
            report = render_design_report(result)
            completion = {'status': 'succeeded', 'result': result, 'report': report}
        except DesignerError as exc:
            completion = {'status': 'failed', 'error': exc.code if exc.code in SAFE_DESIGN_ERRORS else 'design_failed'}
        except Exception:
            # Provider/model content and source prose must never enter diagnostics.
            completion = {'status': 'failed', 'error': 'design_failed'}
        with self.lock:
            self.jobs[job_id].update(completion, _finished=time.monotonic())
            self.active = None

    def job(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise RequestError('job_not_found', 404)
            result = {key: value for key, value in job.items() if not key.startswith('_')}
            result['elapsed_seconds'] = round(max(0, job.get('_finished', time.monotonic()) - job['_started']), 2)
            return result

    def package(self, body):
        shape(body, ('workflows',))
        if type(body['workflows']) is not list or not 1 <= len(body['workflows']) <= 16:
            raise RequestError('invalid_workflows')
        try:
            package = implementation_package(WorkflowRegistry(body['workflows']))
        except (ConfigurationError, TypeError, ValueError, RecursionError):
            raise RequestError('invalid_workflow_configuration') from None
        return {'package': package, 'report': render_report(package['assessment'])}

    def demonstration(self, body):
        shape(body, ('workflow_ids',))
        ids = body['workflow_ids']
        if (type(ids) is not list or not 1 <= len(ids) <= 2 or
                any(type(item) is not str or item not in self.registry.workflows for item in ids) or
                len(set(ids)) != len(ids)):
            raise RequestError('invalid_demo_workflows')
        # This function owns its fresh TemporaryDirectory and builtin adapters.
        return demo(WorkflowRegistry([self.registry.get(item) for item in ids]))


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, studio):
        self.studio = studio
        super().__init__(('127.0.0.1', port), StudioHandler)

    def handle_error(self, request, client_address):
        # Socket resets and malformed requests must not log request data.
        pass


class StudioHandler(BaseHTTPRequestHandler):
    server_version = 'FabricStudio'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    def setup(self):
        self.request.settimeout(BODY_TIMEOUT)
        super().setup()

    def log_message(self, format, *args):
        pass

    def _single_header(self, name):
        values = self.headers.get_all(name, [])
        if len(values) > 1:
            raise RequestError('ambiguous_headers')
        return values[0] if values else None

    def _boundary(self):
        host = self._single_header('Host')
        port = self.server.server_port
        if host not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
            raise RequestError('invalid_host', 403)
        origin = self._single_header('Origin')
        if origin is not None and origin != 'http://' + host:
            raise RequestError('invalid_origin', 403)
        fetch_site = self._single_header('Sec-Fetch-Site')
        if fetch_site is not None and fetch_site not in ('same-origin', 'none'):
            raise RequestError('cross_site_request', 403)
        if self._single_header('Transfer-Encoding') is not None:
            raise RequestError('unsupported_transfer_encoding')
        lengths = self.headers.get_all('Content-Length', [])
        if len(lengths) > 1:
            raise RequestError('ambiguous_headers')
        if self.path.startswith('/api/') and self.path != '/api/bootstrap':
            token = self._single_header('X-Fabric-Session')
            if (token is None or not token.isascii() or
                    not secrets.compare_digest(token, self.server.studio.session_token)):
                raise RequestError('invalid_session', 403)

    def _body(self):
        length = self._single_header('Content-Length')
        if length is None or re.fullmatch(r'[0-9]{1,9}', length) is None:
            raise RequestError('invalid_content_length')
        size = int(length)
        if size > MAX_BODY_BYTES:
            raise RequestError('request_too_large', 413)
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise RequestError('incomplete_body')
        # Consume only the already-bounded body before rejecting its media type.
        # Closing a Windows socket with unread data can otherwise reset the
        # connection before the browser receives the useful 415 diagnostic.
        if self._single_header('Content-Type') not in ('application/json', 'application/json; charset=utf-8'):
            raise RequestError('json_required', 415)
        return strict_json(raw)

    def _respond(self, status, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026').encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', CSP)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        if self.command != 'HEAD':
            self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        self._respond(code, {'error': 'invalid_http_request'})

    def _handle(self):
        try:
            self._boundary()
            app = self.server.studio
            if self.command == 'GET':
                if self.path in STATIC_FILES:
                    name, mime = STATIC_FILES[self.path]
                    data = resources.files('fabric').joinpath('web', name).read_bytes()
                    return self._respond(200, data, mime)
                if self.path == '/api/bootstrap':
                    return self._respond(200, app.bootstrap())
                if self.path == '/api/models':
                    return self._respond(200, app.models())
                if re.fullmatch(r'/api/jobs/[0-9a-f]{32}', self.path):
                    return self._respond(200, app.job(self.path.rsplit('/', 1)[1]))
            elif self.command == 'POST':
                if self.path not in ('/api/design', '/api/package', '/api/demo'):
                    raise RequestError('not_found', 404)
                body = self._body()
                if self.path == '/api/design':
                    return self._respond(202, app.start_design(body))
                if self.path == '/api/package':
                    return self._respond(200, app.package(body))
                return self._respond(200, app.demonstration(body))
            else:
                raise RequestError('method_not_allowed', 405)
            raise RequestError('not_found', 404)
        except RequestError as exc:
            self._respond(exc.status, {'error': exc.code})
        except (TimeoutError, socket.timeout):
            self._respond(408, {'error': 'request_timeout'})
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:
            self._respond(500, {'error': 'request_failed'})

    do_GET = do_POST = do_HEAD = do_PUT = do_DELETE = do_OPTIONS = do_PATCH = _handle


def make_server(port=8765, **options):
    """Create a server; port 0 is useful for isolated real-HTTP tests."""
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('invalid studio port')
    return StudioServer(port, Studio(**options))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--ollama-url', default='http://127.0.0.1:11434')
    parser.add_argument('--model', help='Optional default installed Ollama model')
    browser_options = parser.add_mutually_exclusive_group()
    browser_options.add_argument('--open', action='store_true', help='Open Studio in your default browser')
    browser_options.add_argument('--no-open', action='store_true', help='Print the URL without opening a browser (the default)')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    try:
        server = make_server(args.port, ollama_url=args.ollama_url, model=args.model)
    except (ValueError, OSError):
        parser.error('Could not start Studio; check the port, model endpoint and packaged resources.')
    print(f'Fabric Studio: http://127.0.0.1:{server.server_port}/', flush=True)
    print('Drafts are not approvals. Jobs stay in process memory; descriptions are sent to the configured model endpoint.', flush=True)
    try:
        if args.open:
            webbrowser.open(f'http://127.0.0.1:{server.server_port}/')
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
