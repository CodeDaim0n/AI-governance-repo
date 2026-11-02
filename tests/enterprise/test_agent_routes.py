"""Task authority contract tests. SQLite and simulated identity/FGA, not native PG.
Real native-product acceptance remains separate from these HTTP route assertions.
"""

import tempfile, unittest, json
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fabric.core import Fabric
from fabric.enterprise.agent_routes import install
from fabric.enterprise.app import Action, Execute


class Policy:
    def decide(self, ctx):
        return {"allow": True, "version": "credit-policy-1", "reasons": []}


class Relations:
    def check(self, actor, case):
        return actor == "agent-a" and case == "case-a"

    def close(self):
        pass


class Routes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = Fabric(Path(self.tmp.name) / "case.db", Policy())
        self.f.seed()
        with self.f.tx() as c:
            c.execute(
                "CREATE TABLE agent_tasks(id TEXT PRIMARY KEY,actor TEXT,action TEXT,created DOUBLE PRECISION,expires DOUBLE PRECISION,inspected INT,approval_id TEXT,workflow_id TEXT)"
            )
            c.execute(
                "CREATE TABLE workflow_requests(id TEXT PRIMARY KEY,actor TEXT,action TEXT)"
            )
        self.app = FastAPI()
        self.app.state.fabric = self.f

        def actor(h):
            if h not in ["Bearer agent-a", "Bearer agent-b", "Bearer reviewer-a"]:
                raise HTTPException(401, "identity")
            return h[7:]

        self.calls = []

        def run(who, req):
            self.calls.append((who, req))
            return self.f.execute(who, req.action.model_dump(), req.approval_id)

        install(self.app, actor, run, Action, Execute)
        self.c = TestClient(self.app)
        self.headers = {"Authorization": "Bearer agent-a"}
        self.action = {
            "tool": "credit.commit",
            "case_id": "case-a",
            "amount_pence": 50000,
            "idempotency_key": "task",
        }
        r = self.c.post(
            "/agent/tasks", json={"action": self.action}, headers=self.headers
        )
        self.assertEqual(r.status_code, 200)
        self.tid = r.json()["task_id"]
        self.toolheaders = {**self.headers, "X-Fabric-Task": self.tid}
        self.commit = {k: v for k, v in self.action.items() if k != "tool"}

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_read_precondition_and_exact_commit(self):
        r = self.c.post("/agent/execute", json=self.commit, headers=self.toolheaders)
        self.assertEqual(r.json()["status"], "context_required")
        self.assertEqual(self.calls, [])
        with patch("fabric.enterprise.agent_routes.OpenFGA", Relations):
            r = self.c.post(
                "/inspect", json={"case_id": "case-a"}, headers=self.toolheaders
            )
            self.assertEqual(r.status_code, 200)
        r = self.c.post("/agent/execute", json=self.commit, headers=self.toolheaders)
        self.assertEqual(r.json()["status"], "executed")
        self.assertEqual(len(self.calls), 1)

    def test_other_principal_cannot_read_task_or_change_intent(self):
        r = self.c.post(
            "/inspect",
            json={"case_id": "case-a"},
            headers={**self.toolheaders, "Authorization": "Bearer agent-b"},
        )
        self.assertEqual(r.status_code, 404)
        r = self.c.post(
            "/agent/execute",
            json={**self.commit, "amount_pence": 999999},
            headers=self.toolheaders,
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.calls, [])

    def test_inspection_must_match_bound_case_and_relationship(self):
        r = self.c.post(
            "/inspect", json={"case_id": "case-b"}, headers=self.toolheaders
        )
        self.assertEqual(r.status_code, 403)

        class NoRelations(Relations):
            def check(self, *a):
                return False

        with patch("fabric.enterprise.agent_routes.OpenFGA", NoRelations):
            r = self.c.post(
                "/inspect", json={"case_id": "case-a"}, headers=self.toolheaders
            )
            self.assertEqual(r.status_code, 403)
        self.assertEqual(
            self.c.post(
                "/agent/execute", json=self.commit, headers=self.toolheaders
            ).json()["status"],
            "context_required",
        )

    def test_expiry_rechecked_and_reviewers_cannot_create_agent_task(self):
        with self.f.tx() as c:
            c.execute("UPDATE agent_tasks SET expires=0")
        self.assertEqual(
            self.c.post(
                "/agent/execute", json=self.commit, headers=self.toolheaders
            ).status_code,
            410,
        )
        self.assertEqual(
            self.c.post(
                "/agent/tasks",
                json={"action": self.action},
                headers={"Authorization": "Bearer reviewer-a"},
            ).status_code,
            403,
        )

    def test_model_success_narrative_does_not_become_execution_status(self):
        class ClaimingAgent:
            def __init__(self, *a, **kw):
                pass

            def run(self, *a):
                return {
                    "stop_reason": "model_final",
                    "final": "Successfully completed and approved",
                    "tool_events": [],
                }

        with (
            patch.dict(
                "os.environ",
                {
                    "OLLAMA_URL": "http://model",
                    "OLLAMA_MODEL": "qwen-fixture",
                    "GATEWAY_URL": "http://gateway",
                },
            ),
            patch("fabric.enterprise.agent_routes.Agent", ClaimingAgent),
        ):
            response = self.c.post(
                "/agent/tasks/" + self.tid + "/run", headers=self.headers
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["execution"]["status"], "not_executed")
        self.assertEqual(
            self.c.get("/agent/tasks/" + self.tid, headers=self.headers).json()[
                "execution"
            ]["status"],
            "not_executed",
        )
        self.assertEqual(self.calls, [])

    def test_unlisted_tool_fields_and_missing_task_cannot_execute(self):
        self.assertEqual(
            self.c.post(
                "/agent/execute",
                json={**self.commit, "approved": True},
                headers=self.toolheaders,
            ).status_code,
            422,
        )
        self.assertEqual(
            self.c.post(
                "/agent/execute", json=self.commit, headers=self.headers
            ).status_code,
            404,
        )
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
