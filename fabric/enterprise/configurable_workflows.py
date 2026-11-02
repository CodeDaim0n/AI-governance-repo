"""Generic durable approval journey; policy decisions stay at the gateway.

Workflow inputs must come from an authenticated, scoped application. The worker
uses its own configured delegation; it never accepts a token or endpoint in input.
"""
import asyncio
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    import httpx
    from .clients import Keycloak, required


@activity.defn
async def submit_governed_operation(request):
    identity = Keycloak()
    try:
        token = await asyncio.to_thread(identity.token, required("FABRIC_WORKER_CLIENT_ID"),
                                       required("AGENT_CLIENT_SECRET"))
        actor = await asyncio.to_thread(identity.verify, token)
        if actor != request["actor"]:
            raise ValueError("Workflow worker delegation does not match bound actor")
    finally:
        identity.close()
    async with httpx.AsyncClient(timeout=30, follow_redirects=False, trust_env=False) as client:
        response = await client.post(required("GATEWAY_URL").rstrip("/") + "/execute",
            json={"action": request["action"], "approval_id": request.get("approval_id")},
            headers={"Authorization": "Bearer " + token})
        response.raise_for_status()
        result = response.json()
    if not isinstance(result, dict) or result.get("status") not in {"executed", "denied"}:
        raise ValueError("Malformed gateway decision")
    return result


@workflow.defn
class GovernedOperation:
    def __init__(self):
        self.approval_id = None

    @workflow.signal(name="approval")
    def approval(self, reference: str):
        # A signal is a reference only. It does not grant approval authority.
        if isinstance(reference, str) and 0 < len(reference) <= 128:
            self.approval_id = reference

    @workflow.run
    async def run(self, request: dict):
        if set(request) != {"action", "actor", "approval_timeout_seconds"}:
            raise ValueError("Invalid workflow request")
        timeout = request["approval_timeout_seconds"]
        if type(timeout) is not int or not 1 <= timeout <= 86400:
            raise ValueError("Invalid approval timeout")

        async def submit():
            return await workflow.execute_activity(submit_governed_operation,
                {"action": request["action"], "actor": request["actor"], "approval_id": self.approval_id},
                start_to_close_timeout=timedelta(seconds=45),
                retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=2)))

        result = await submit()
        if result["status"] == "executed":
            return result
        reasons = set(result.get("reason", "").split(","))
        if reasons != {"approval_required"}:
            return result
        try:
            await workflow.wait_condition(lambda: self.approval_id is not None,
                                          timeout=timedelta(seconds=timeout))
        except asyncio.TimeoutError:
            return {"status": "expired", "reason": "human_approval_timeout"}
        return await submit()


async def main():
    from temporalio.client import Client
    from temporalio.worker import Worker
    client = await Client.connect(required("TEMPORAL_ADDRESS"))
    async with Worker(client, task_queue=required("FABRIC_TASK_QUEUE"),
                      workflows=[GovernedOperation], activities=[submit_governed_operation]):
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
