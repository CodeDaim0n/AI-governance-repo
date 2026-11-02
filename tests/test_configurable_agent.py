"""Simulated model outputs against a real local JWT-authenticated generic gateway.

These tests verify boundaries and synthetic effects, not live model competence.
"""

import copy
from contextlib import closing
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from fabric.adapters import builtin_adapters
from fabric.auth import issue
from fabric.configuration import WorkflowRegistry
from fabric.configurable_agent import ConfigurableAgent
from fabric.configurable_server import make_handler
from fabric.runtime import ConfigurableFabric


ROOT = Path(__file__).resolve().parents[1]


class ConfigurableAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        cls.public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        registry = WorkflowRegistry.from_paths([ROOT / "workflows/synthetic-credit.json", ROOT / "workflows/it-access.json"])
        self.fabric = ConfigurableFabric(Path(self.temp.name) / "agent.db", registry, adapters=builtin_adapters())
        self.fabric.provision_demo()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.fabric, self.public))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port)
        self.token = issue(self.private, "agent-a")
        self.client = httpx.Client(base_url=self.url, trust_env=False, headers={"Authorization": "Bearer " + self.token})

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    @staticmethod
    def credit(key="credit", amount=5000):
        return {"workflow_id": "synthetic-credit", "operation": "commit_credit", "resource_id": "case-a", "parameters": {"amount_pence": amount, "reason": "fixture"}, "idempotency_key": key}

    @staticmethod
    def access(key="access", permission="read"):
        return {"workflow_id": "it-access", "operation": "grant_access", "resource_id": "employee-a", "parameters": {"permission": permission, "duration_hours": 4, "justification": "fixture"}, "idempotency_key": key}

    @staticmethod
    def call(name, arguments):
        return {"function": {"name": name, "arguments": arguments}}

    def inspect_call(self, action):
        return self.call("inspect_resource", {key: action[key] for key in ("workflow_id", "resource_id")})

    def run_model(self, action, calls, *, task=None, max_calls=8):
        if task is None:
            response = self.client.post("/agent/tasks", json={"action": action})
            self.assertEqual(response.status_code, 200, response.text)
            task = response.json()["task_id"]
        self.model_requests = []

        def simulate(request):
            self.model_requests.append(request)
            return httpx.Response(200, json={"message": {"role": "assistant", "content": "", "tool_calls": calls}})

        result = ConfigurableAgent(
            "http://simulated-model", "simulated-fixture", self.url, self.token,
            task_id=task, model_transport=httpx.MockTransport(simulate), max_calls=max_calls, max_turns=2,
        ).run()
        return task, result

    def test_same_agent_runs_credit_and_access_with_generated_schemas(self):
        for action in (self.credit(), self.access()):
            with self.subTest(workflow=action["workflow_id"]):
                _, result = self.run_model(action, [self.inspect_call(action), self.call("execute_operation", action)])
                self.assertEqual(result["stop_reason"], "executed")
                self.assertEqual(result["execution"]["status"], "executed")
                payload = json.loads(self.model_requests[0].content)
                fields = payload["tools"][1]["function"]["parameters"]["properties"]["parameters"]["properties"]
                self.assertEqual(set(fields), set(action["parameters"]))
                self.assertNotIn("Authorization", self.model_requests[0].headers)
                self.assertNotIn(self.token, json.dumps(result))
                self.assertNotIn(self.token, self.model_requests[0].content.decode())

    def test_approval_requires_separate_reviewer_and_resumes_same_task(self):
        action = self.access(permission="admin")
        calls = [self.inspect_call(action), self.call("execute_operation", action)]
        task, result = self.run_model(action, calls)
        self.assertEqual(result["stop_reason"], "waiting_approval")
        response = self.client.post("/agent/tasks/" + task + "/approve", json={}, headers={"Authorization": "Bearer " + issue(self.private, "reviewer-a")})
        self.assertEqual(response.status_code, 200, response.text)
        _, result = self.run_model(action, calls, task=task)
        self.assertEqual(result["execution"]["status"], "executed")

    def test_model_cannot_substitute_intent_or_add_authority(self):
        action = self.credit()
        altered = copy.deepcopy(action)
        altered["parameters"]["amount_pence"] = 1
        variants = [
            self.call("execute_operation", altered),
            self.call("execute_operation", {**action, "approval_id": "invented"}),
            self.call("execute_operation", {**action, "actor": "admin-a"}),
            self.call("execute_operation", {**action, "target_url": "https://attacker.invalid"}),
            self.call("execute_operation", self.access()),
            self.call("shell.exec", {"command": "whoami"}),
        ]
        for call in variants:
            with self.subTest(call=call):
                _, result = self.run_model(action, [self.inspect_call(action), call])
                self.assertEqual(result["stop_reason"], "denied")
                self.assertEqual(result["tool_events"][-1]["observation"]["reason"], "tool_schema_or_intent")
        with closing(self.fabric.connect()) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM cfg_effects").fetchone()[0], 0)

    def test_execute_before_inspect_is_denied_locally(self):
        action = self.credit()
        _, result = self.run_model(action, [self.call("execute_operation", action), self.inspect_call(action)])
        self.assertEqual(result["stop_reason"], "denied")
        self.assertEqual(result["calls"], 1)
        self.assertEqual(result["tool_events"][0]["observation"]["reason"], "inspection_required")

    def test_denial_stops_remaining_calls_and_claims_do_not_create_receipts(self):
        action = self.credit()
        _, denied = self.run_model(action, [self.call("approve", {}), self.inspect_call(action)])
        self.assertEqual(denied["calls"], 1)
        _, final = self.run_model(action, [])
        self.assertEqual(final["execution"]["status"], "not_executed")
        self.assertEqual(final["stop_reason"], "model_final")

    def test_tool_call_budget_applies_within_one_model_response(self):
        action = self.credit()
        _, result = self.run_model(action, [self.inspect_call(action)] * 6, max_calls=2)
        self.assertEqual(result["calls"], 2)
        self.assertEqual(result["stop_reason"], "tool_budget")
        self.assertEqual(result["execution"]["status"], "not_executed")

    def test_model_tool_json_cannot_use_boolean_for_integer(self):
        action = self.credit(amount=1)
        altered = copy.deepcopy(action)
        altered["parameters"]["amount_pence"] = True
        _, result = self.run_model(action, [self.inspect_call(action), self.call("execute_operation", altered)])
        self.assertEqual(result["tool_events"][-1]["observation"]["reason"], "tool_schema_or_intent")


if __name__ == "__main__":
    unittest.main()
