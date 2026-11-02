"""Native-process experiment gateway, not a replacement for enterprise.app.
Real Keycloak/OpenFGA/OPA/AGT/Bao integrations; SQLite synthetic target.
Server-owned intent binding is provisioned by the experiment controller.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from prometheus_client import Counter, generate_latest, CollectorRegistry
from fabric.core import Fabric, OPA, Rejected
from fabric.microsoft_agt import wrap
from fabric.enterprise.clients import Keycloak, OpenFGA, DependencyFailure
from opentelemetry import trace


class NativePolicy:
    def __init__(self, fga, opa_url):
        self.fga = fga
        self.opa = OPA(opa_url)

    def decide(self, ctx):
        if not self.fga.check(ctx["principal"]["id"], ctx["action"]["case_id"]):
            return {
                "allow": False,
                "version": "credit-policy-1",
                "reasons": ["relationship_denied"],
            }
        return self.opa.decide(ctx)


class Lab:
    def __init__(self, require_inspection=False):
        self.require_inspection = require_inspection
        self.inspected = False
        self.approval_required = None
        self.workflow_status = None
        self.kc = Keycloak()
        self.fga = OpenFGA()
        self.fabric = None
        self.intent = None
        self.source_note = "Synthetic case facts."
        self.approval = None
        self.registry = CollectorRegistry()
        self.decisions = Counter(
            "fabric_native_decisions",
            "Synthetic governed results",
            ["outcome"],
            registry=self.registry,
        )
        self.tracer = trace.get_tracer("fabric.native-lab")
        self.alerts = []

    def bind(self, fabric, intent):
        self.fabric = fabric
        self.intent = dict(intent)
        self.approval = None
        self.inspected = False
        self.approval_required = None
        self.workflow_status = None
        self.source_note = "Synthetic case facts."

    def handler(self):
        lab = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path == "/metrics":
                    data = generate_latest(lab.registry)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; version=0.0.4")
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self.reply(404, {"error": "unknown_route"})

            def do_POST(self):
                try:
                    n = int(self.headers.get("Content-Length", 0))
                    if not 0 < n <= 16384:
                        raise Rejected("body_size")
                    body = json.loads(self.rfile.read(n))
                    if self.path == "/alerts":
                        # Synthetic alert receiver is loopback-only; full enterprise receiver uses a bearer secret.
                        lab.alerts.append(body)
                        self.reply(200, {"accepted": True})
                        return
                    auth = self.headers.get("Authorization", "")
                    if not auth.startswith("Bearer "):
                        raise Rejected("token_required")
                    actor = lab.kc.verify(auth[7:])
                    with lab.tracer.start_as_current_span(
                        "governed-agent-tool"
                    ) as span:
                        span.set_attribute("fabric.operation", self.path)
                        if self.path == "/inspect":
                            if set(body) != {"case_id"}:
                                raise Rejected("invalid_schema")
                            with lab.fabric.connect() as c:
                                p = lab.fabric.principal(c, actor)
                                case = c.execute(
                                    "SELECT * FROM cases WHERE id=?", (body["case_id"],)
                                ).fetchone()
                            if (
                                not case
                                or p["tenant"] != case["tenant"]
                                or not lab.fga.check(actor, body["case_id"])
                            ):
                                raise Rejected("source_access_denied")
                            lab.inspected = True
                            result = {
                                "status": "observed",
                                "case": dict(case),
                                "source_note": lab.source_note,
                            }
                        elif self.path in ("/agent/execute", "/execute", "/approve"):
                            action = (
                                {"tool": "credit.commit", **body}
                                if self.path == "/agent/execute"
                                else body["action"]
                            )
                            if action != lab.intent:
                                raise Rejected("intent_binding_mismatch")
                            if (
                                self.path == "/agent/execute"
                                and lab.require_inspection
                                and not lab.inspected
                            ):
                                self.reply(
                                    200,
                                    {
                                        "status": "context_required",
                                        "reason": "Read authorized case context before requesting commitment",
                                        "next_tool": "inspect_case",
                                        "case_id": lab.intent["case_id"],
                                    },
                                )
                                return
                            if self.path == "/approve":
                                result = {
                                    "approval_id": lab.fabric.approve(
                                        actor, "agent-a", action
                                    )
                                }
                            elif self.path == "/agent/execute" and lab.workflow_status:
                                if actor != "agent-a":
                                    raise Rejected("task_actor_mismatch")
                                result = lab.workflow_status()
                            else:
                                approval = (
                                    lab.approval
                                    if self.path == "/agent/execute"
                                    else body.get("approval_id")
                                )
                                result = wrap(lab.fabric, actor)(
                                    action=action["tool"],
                                    proposal=action,
                                    approval_id=approval,
                                )
                                if (
                                    self.path == "/agent/execute"
                                    and result.get("reason")
                                    == "human_approval_required"
                                    and lab.approval_required
                                ):
                                    result = lab.approval_required(action)
                        else:
                            raise Rejected("route_not_allowed")
                        lab.decisions.labels(result.get("status", "approved")).inc()
                        span.set_attribute(
                            "fabric.outcome", result.get("status", "approved")
                        )
                        self.reply(200, result)
                except Rejected as e:
                    lab.decisions.labels("denied").inc()
                    self.reply(403, {"error": str(e)})
                except DependencyFailure:
                    self.reply(503, {"error": "authority_unavailable"})
                except (ValueError, KeyError, TypeError):
                    self.reply(400, {"error": "invalid_request"})
                except Exception:
                    self.reply(503, {"error": "dependency_or_storage_failure"})

        return Handler
