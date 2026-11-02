"""Task-scoped autonomous tool routes for the commissioned native gateway.
The agent proposes calls. Identity, task scope, read preconditions, authority,
approval and durable workflow state remain server-owned.
"""

import asyncio, json, uuid
from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr
from fabric.agent import Agent
from fabric.core import canonical, Rejected, digest
from .clients import OpenFGA, required, DependencyFailure


class CaseRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: StrictStr


class Commit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: StrictStr
    amount_pence: StrictInt
    idempotency_key: StrictStr


def install(app, actor, run_action, Action, Execute):
    def task(task_id, who):
        f = app.state.fabric
        with f.connect() as c:
            try:
                f.principal(c, who)
            except Rejected as e:
                raise HTTPException(403, str(e))
            row = c.execute(
                "SELECT * FROM agent_tasks WHERE id=? AND actor=?", (task_id, who)
            ).fetchone()
        if not row:
            raise HTTPException(404, "Unknown task")
        if row["expires"] <= f.clock():
            raise HTTPException(410, "Task expired")
        return dict(row)

    def outcome(bound):
        f = app.state.fabric
        intent = json.loads(bound["action"])
        with f.connect() as c:
            principal = f.principal(c, bound["actor"])
            receipt = c.execute(
                "SELECT hash,response FROM actions WHERE actor=? AND tenant=? AND idem=?",
                (bound["actor"], principal["tenant"], intent["idempotency_key"]),
            ).fetchone()
        if receipt:
            if receipt["hash"] != digest(intent):
                return {"status": "denied", "reason": "idempotency_conflict"}
            return json.loads(receipt["response"])
        if bound["workflow_id"]:
            return {"status": "workflow_pending", "workflow_id": bound["workflow_id"]}
        return {"status": "not_executed"}

    @app.get("/agent/tasks/{task_id}")
    async def task_status(
        task_id: str, authorization: str | None = Header(default=None)
    ):
        bound = task(task_id, actor(authorization))
        return {
            "task_id": task_id,
            "expires": bound["expires"],
            "action": json.loads(bound["action"]),
            "execution": outcome(bound),
        }

    @app.post("/agent/tasks")
    async def create_task(
        request: Execute, authorization: str | None = Header(default=None)
    ):
        who = actor(authorization)
        f = app.state.fabric
        try:
            f.validate(request.action.model_dump())
            with f.tx() as c:
                principal = f.principal(c, who)
                if principal["role"] != "agent":
                    raise HTTPException(403, "Agent principal required")
                tid = str(uuid.uuid4())
                expires = f.clock() + 600
                c.execute(
                    "INSERT INTO agent_tasks VALUES(?,?,?,?,?,0,?,NULL)",
                    (
                        tid,
                        who,
                        canonical(request.action.model_dump()),
                        f.clock(),
                        expires,
                        request.approval_id,
                    ),
                )
        except Rejected as e:
            raise HTTPException(403, str(e))
        return {"task_id": tid, "expires": expires, "status": "created"}

    @app.post("/agent/tasks/{task_id}/run")
    async def run(task_id: str, authorization: str | None = Header(default=None)):
        who = actor(authorization)
        bound = task(task_id, who)
        # Only a typed, server-stored action enters the prompt. Task ID is an HTTP
        # header, never a model-controlled tool parameter. No target or reviewer secret.
        prompt = "Perform this exact synthetic action: " + canonical(
            {k: v for k, v in json.loads(bound["action"]).items() if k != "tool"}
        )
        agent = Agent(
            required("OLLAMA_URL"),
            required("OLLAMA_MODEL"),
            required("GATEWAY_URL"),
            authorization[7:],
            task_id=task_id,
        )
        result = await asyncio.to_thread(agent.run, prompt)
        current = task(task_id, who)
        return {
            "task_id": task_id,
            "workflow_id": current["workflow_id"],
            "execution": outcome(current),
            "agent": result,
        }

    @app.post("/inspect")
    async def inspect(
        request: CaseRead,
        authorization: str | None = Header(default=None),
        x_fabric_task: str | None = Header(default=None),
    ):
        who = actor(authorization)
        bound = task(x_fabric_task, who)
        intent = json.loads(bound["action"])
        if request.case_id != intent["case_id"]:
            raise HTTPException(403, "Task case mismatch")
        f = app.state.fabric
        with f.connect() as c:
            principal = f.principal(c, who)
            row = c.execute(
                "SELECT * FROM cases WHERE id=?", (request.case_id,)
            ).fetchone()
        if not row or principal["tenant"] != row["tenant"]:
            raise HTTPException(403, "Source access denied")
        fga = OpenFGA()
        try:
            if not await asyncio.to_thread(fga.check, who, request.case_id):
                raise HTTPException(403, "Source relationship denied")
        except DependencyFailure:
            raise HTTPException(503, "Relationship authority unavailable")
        finally:
            fga.close()
        with f.tx() as c:
            c.execute(
                "UPDATE agent_tasks SET inspected=1 WHERE id=? AND actor=?",
                (x_fabric_task, who),
            )
        return {
            "status": "observed",
            "case": {k: row[k] for k in ("id", "kyc", "region", "version", "updated")},
        }

    @app.post("/agent/execute")
    async def commit(
        request: Commit,
        authorization: str | None = Header(default=None),
        x_fabric_task: str | None = Header(default=None),
    ):
        who = actor(authorization)
        bound = task(x_fabric_task, who)
        intent = json.loads(bound["action"])
        proposed = {"tool": "credit.commit", **request.model_dump()}
        if proposed != intent:
            raise HTTPException(403, "Task intent mismatch")
        if not bound["inspected"]:
            return {
                "status": "context_required",
                "next_tool": "inspect_case",
                "case_id": intent["case_id"],
            }
        if bound["workflow_id"]:
            from temporalio.client import Client

            c = await Client.connect(required("TEMPORAL_ADDRESS"))
            h = c.get_workflow_handle(bound["workflow_id"])
            description = await h.describe()
            if description.status.name == "COMPLETED":
                return await h.result()
            if description.status.name != "RUNNING":
                return {
                    "status": "denied",
                    "reason": "workflow_" + description.status.name.lower(),
                }
            return {"status": "waiting_approval", "workflow_id": bound["workflow_id"]}
        result = await asyncio.to_thread(
            run_action,
            who,
            Execute(action=Action(**intent), approval_id=bound["approval_id"]),
        )
        if (
            result.get("status") != "denied"
            or result.get("reason") != "human_approval_required"
        ):
            return result
        if who != "agent-a":
            raise HTTPException(
                403, "Configured durable worker is delegated to agent-a only"
            )
        from temporalio.client import Client
        from temporalio.exceptions import WorkflowAlreadyStartedError
        from .workflows import GovernedCredit

        wid = "fabric-agent-task-" + x_fabric_task
        with app.state.fabric.tx() as c:
            old = c.execute(
                "SELECT id FROM workflow_requests WHERE id=?", (wid,)
            ).fetchone()
            if not old:
                c.execute(
                    "INSERT INTO workflow_requests VALUES(?,?,?)",
                    (wid, who, canonical(intent)),
                )
        client = await Client.connect(required("TEMPORAL_ADDRESS"))
        try:
            await client.start_workflow(
                GovernedCredit.run,
                {"action": intent},
                id=wid,
                task_queue="fabric-credit",
            )
        except WorkflowAlreadyStartedError:
            pass
        with app.state.fabric.tx() as c:
            c.execute(
                "UPDATE agent_tasks SET workflow_id=? WHERE id=? AND actor=?",
                (wid, x_fabric_task, who),
            )
        return {"status": "waiting_approval", "workflow_id": wid}
