"""Adversarial agent boundary tests with explicit simulated inference/HTTP.
Native model transcripts are a separate experiment, not these unit assertions.
"""

import json, unittest
from unittest.mock import patch
import httpx
from fabric.agent import Agent


class AgentBoundary(unittest.TestCase):
    def run_agent(self, calls, **kw):
        self.requests = []

        def route(request):
            self.requests.append(request)
            if request.url.host == "model":
                return httpx.Response(
                    200,
                    json={
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": calls,
                        }
                    },
                )
            return httpx.Response(
                200, json={"status": "executed", "action_id": "fixture"}
            )

        client = httpx.Client(transport=httpx.MockTransport(route))
        with patch("fabric.agent.httpx.Client", return_value=client):
            return Agent(
                "http://model", "qwen-fixture", "http://gateway", "private-token", **kw
            ).run("task")

    def test_unknown_tool_never_crosses_gateway(self):
        r = self.run_agent(
            [{"function": {"name": "shell.exec", "arguments": {"cmd": "whoami"}}}],
            max_turns=1,
        )
        self.assertEqual(
            r["tool_events"][0]["observation"]["reason"], "tool_schema_or_name"
        )
        self.assertEqual(len(self.requests), 1)

    def test_reviewer_fields_rejected(self):
        r = self.run_agent(
            [
                {
                    "function": {
                        "name": "commit_action",
                        "arguments": {
                            "case_id": "a",
                            "amount_pence": 1,
                            "idempotency_key": "x",
                            "approved": True,
                        },
                    }
                }
            ],
            max_turns=1,
        )
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(r["calls"], 1)

    def test_calls_budget_limits_same_reply_and_future_turns(self):
        call = {"function": {"name": "inspect_case", "arguments": {"case_id": "a"}}}
        r = self.run_agent([call] * 9, max_calls=2, max_turns=4)
        self.assertEqual(r["calls"], 2)
        self.assertEqual(r["stop_reason"], "tool_budget")
        self.assertEqual(len(self.requests), 3)

    def test_token_only_sent_to_gateway_never_model(self):
        r = self.run_agent(
            [{"function": {"name": "inspect_case", "arguments": {"case_id": "a"}}}],
            max_turns=1,
        )
        model, gateway = self.requests
        self.assertNotIn("private-token", model.content.decode())
        self.assertNotIn("authorization", model.headers)
        self.assertEqual(gateway.headers["authorization"], "Bearer private-token")

    def test_malformed_function_denied_without_crash(self):
        r = self.run_agent([{"function": "bad"}, None], max_turns=1)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(r["calls"], 2)

    def test_no_tool_call_is_final_not_fabricated_success(self):
        r = self.run_agent([], max_turns=1)
        self.assertEqual(r["stop_reason"], "model_final")
        self.assertEqual(r["tool_events"], [])


if __name__ == "__main__":
    unittest.main()
