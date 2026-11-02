"""Real local HTTP and signed JWT tests; effects use explicit synthetic adapters."""

import copy
from contextlib import closing
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from fabric.adapters import builtin_adapters
from fabric.auth import issue
from fabric.configuration import WorkflowRegistry
from fabric.configurable_server import make_handler
from fabric.runtime import ConfigurableFabric


ROOT = Path(__file__).resolve().parents[1]


class ConfigurableAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        cls.public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = time.time()
        self.registry = WorkflowRegistry.from_paths([ROOT / "workflows/synthetic-credit.json", ROOT / "workflows/it-access.json"])
        self.fabric = ConfigurableFabric(Path(self.temp.name) / "api.db", self.registry, adapters=builtin_adapters(), clock=lambda: self.now)
        self.fabric.provision_demo()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.fabric, self.public))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = httpx.Client(base_url="http://127.0.0.1:" + str(self.server.server_port), trust_env=False)

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

    def request(self, route, body=None, *, actor="agent-a", task=None, method="POST"):
        headers = {"Authorization": "Bearer " + issue(self.private, actor)}
        if task:
            headers["X-Fabric-Task"] = task
        return self.client.request(method, route, json=body, headers=headers)

    def create_task(self, action):
        response = self.request("/agent/tasks", {"action": action})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["task_id"]

    def inspect_task(self, task, action):
        body = {key: action[key] for key in ("workflow_id", "resource_id")}
        response = self.request("/agent/inspect", body, task=task)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "observed")

    def test_two_distinct_workflows_share_authenticated_execution(self):
        for action in (self.credit(), self.access()):
            with self.subTest(workflow=action["workflow_id"]):
                response = self.request("/execute", {"action": action})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["status"], "executed")
                self.assertEqual(self.request("/execute", {"action": action}).json(), response.json())
        with closing(self.fabric.connect()) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM cfg_effects").fetchone()[0], 2)
        self.assertTrue(self.fabric.verify_chain())

    def test_separate_review_approval_then_execution(self):
        for action in (self.credit(amount=20000), self.access(permission="admin")):
            response = self.request("/execute", {"action": action})
            self.assertIn("approval_required", response.json()["reason"])
            self.assertEqual(self.request("/approve", {"actor": "agent-a", "action": action}).status_code, 403)
            approval = self.request("/approve", {"actor": "agent-a", "action": action}, actor="reviewer-a").json()["approval_id"]
            response = self.request("/execute", {"action": action, "approval_id": approval})
            self.assertEqual(response.json()["status"], "executed")

    def test_invalid_or_expired_signed_token_fails(self):
        self.assertEqual(self.client.post("/execute", json={"action": self.credit()}).status_code, 403)
        token = issue(self.private, "agent-a", lifetime=-1)
        response = self.client.post("/execute", json={"action": self.credit()}, headers={"Authorization": "Bearer " + token})
        self.assertEqual(response.json()["error"], "invalid_token")
        self.assertEqual(self.request("/execute", {"action": self.credit()}, actor="unprovisioned").status_code, 403)

    def test_strict_json_and_envelope_reject_identity_and_ambiguous_body(self):
        headers = {"Authorization": "Bearer " + issue(self.private, "agent-a"), "Content-Type": "application/json"}
        for body in ('{"action":{},"action":{}}', '{"action":NaN}', '{"action":1e9999}', '[{}]', '{"action":' + json.dumps(self.credit()) + ',"actor":"admin-a"}'):
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/execute", content=body, headers=headers).status_code, 400)
        self.assertEqual(self.client.post("/execute", content=" " * 17000, headers=headers).status_code, 400)
        headers["Content-Type"] = "text/plain"
        self.assertEqual(self.client.post("/execute", content='{"action":{}}', headers=headers).status_code, 400)

    def test_task_enforces_inspect_first_and_exact_action(self):
        action = self.credit()
        task = self.create_task(action)
        self.assertEqual(self.request("/agent/execute", action, task=task).json()["error"], "inspection_required")
        self.inspect_task(task, action)
        altered = copy.deepcopy(action)
        altered["parameters"]["amount_pence"] += 1
        self.assertEqual(self.request("/agent/execute", altered, task=task).json()["error"], "task_intent_mismatch")
        self.assertEqual(self.request("/agent/execute", {**action, "approval_id": "invented"}, task=task).status_code, 403)
        result = self.request("/agent/execute", action, task=task).json()
        self.assertEqual(result["status"], "executed")
        current = self.request("/agent/tasks/" + task, method="GET").json()
        self.assertEqual(current["execution"], result)
        schema = current["tools"][1]["function"]["parameters"]["properties"]["parameters"]
        self.assertEqual(set(schema["properties"]), {"amount_pence", "reason"})

    def test_cross_task_workflow_and_actor_substitution_denied(self):
        first, second = self.credit(), self.access()
        task = self.create_task(first)
        other_task = self.create_task(second)
        self.assertEqual(self.request("/agent/tasks/" + task, actor="agent-b", method="GET").status_code, 403)
        self.assertEqual(self.request("/agent/inspect", {"workflow_id": second["workflow_id"], "resource_id": second["resource_id"]}, task=task).status_code, 403)
        self.inspect_task(task, first)
        self.assertEqual(self.request("/agent/execute", second, task=task).status_code, 403)
        self.assertEqual(self.request("/agent/execute", second, task=other_task).json()["error"], "inspection_required")

    def test_task_approval_is_bound_and_survives_handler_restart(self):
        action = self.access(permission="admin")
        task = self.create_task(action)
        self.inspect_task(task, action)
        self.assertEqual(self.request("/agent/execute", action, task=task).json()["status"], "denied")
        route = "/agent/tasks/" + task + "/approve"
        self.assertEqual(self.request(route, {}).status_code, 403)
        self.assertEqual(self.request(route, {}, actor="reviewer-b").status_code, 403)
        self.assertEqual(self.request(route, {}, actor="reviewer-a").json()["status"], "approved")
        self.server.RequestHandlerClass = make_handler(self.fabric, self.public)
        self.assertEqual(self.request("/agent/execute", action, task=task).json()["status"], "executed")

    def test_task_expiry_and_configuration_change_fail_closed(self):
        task = self.create_task(self.credit())
        self.now += 601
        self.assertEqual(self.request("/agent/tasks/" + task, method="GET").json()["error"], "task_expired")
        self.now -= 601
        profiles = [value.to_dict() for value in self.registry.workflows.values()]
        profiles[0]["description"] += " changed"
        self.fabric.registry = WorkflowRegistry(profiles)
        self.assertEqual(self.request("/agent/tasks/" + task, method="GET").json()["error"], "task_configuration_changed")

    def test_stop_is_workflow_scoped_and_admin_only(self):
        body = {"workflow_id": "synthetic-credit", "stopped": True}
        self.assertEqual(self.request("/stop", body).status_code, 403)
        self.assertEqual(self.request("/stop", body, actor="admin-a").status_code, 200)
        self.assertEqual(self.request("/execute", {"action": self.credit()}).json()["status"], "denied")
        self.assertEqual(self.request("/execute", {"action": self.access()}).json()["status"], "executed")

    def test_reprovisioned_identity_cannot_reuse_previous_task(self):
        task = self.create_task(self.credit())
        self.fabric.provision_principal("agent-a", "demo-org", "agent")
        self.assertEqual(self.request("/agent/tasks/" + task, method="GET").json()["error"], "task_identity_changed")

    def test_queued_execution_rechecks_task_expiry_inside_runtime_transaction(self):
        action = self.credit()
        task = self.create_task(action)
        self.inspect_task(task, action)
        execute = self.fabric.execute

        def queued(*args, **kwargs):
            self.now += 601
            return execute(*args, **kwargs)

        with patch.object(self.fabric, "execute", side_effect=queued):
            response = self.request("/agent/execute", action, task=task)
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()["error"], "task_expired")
        with closing(self.fabric.connect()) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM cfg_effects").fetchone()[0], 0)

    def test_queued_execution_rechecks_reprovisioned_identity(self):
        action = self.credit()
        task = self.create_task(action)
        self.inspect_task(task, action)
        execute = self.fabric.execute

        def queued(*args, **kwargs):
            self.fabric.provision_principal("agent-a", "demo-org", "agent")
            return execute(*args, **kwargs)

        with patch.object(self.fabric, "execute", side_effect=queued):
            response = self.request("/agent/execute", action, task=task)
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()["error"], "task_identity_changed")
        with closing(self.fabric.connect()) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM cfg_effects").fetchone()[0], 0)

    def test_task_expiring_during_policy_wait_cannot_apply_effect(self):
        action = self.credit()
        task = self.create_task(action)
        self.inspect_task(task, action)

        def decide(_):
            self.now += 601
            return {"allow": True}

        class Policy:
            pass

        policy = Policy()
        policy.decide = decide
        self.fabric.policy = policy
        response = self.request("/agent/execute", action, task=task)
        self.assertEqual(response.json().get("reason", response.json().get("error")), "task_expired")
        with closing(self.fabric.connect()) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM cfg_effects").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
