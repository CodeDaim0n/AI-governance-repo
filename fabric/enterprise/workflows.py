"""Durable Temporal workflow. Activity retries rely on target idempotency."""
import asyncio
from datetime import timedelta
from temporalio import workflow,activity
from temporalio.common import RetryPolicy
with workflow.unsafe.imports_passed_through():
 import os,httpx
 from .clients import Keycloak,required

@activity.defn
async def commit_action(request):
 # Tokens are obtained within an Activity, never serialized into workflow history.
 kc=Keycloak()
 try:token=await asyncio.to_thread(kc.token,'fabric-agent',required('AGENT_CLIENT_SECRET'))
 finally:kc.close()
 async with httpx.AsyncClient(timeout=30,trust_env=False) as c:
  response=await c.post(required('GATEWAY_URL')+'/execute',json=request,headers={'Authorization':'Bearer '+token})
  response.raise_for_status();result=response.json()
  if result.get('status')!='executed':
   from temporalio.exceptions import ApplicationError
   raise ApplicationError('Business policy denied action',non_retryable=True)
  return result

@workflow.defn
class GovernedCredit:
 def __init__(self):self.approval_id=None
 @workflow.signal(name='approval')
 def approval(self,reference:str):
  # Signals only carry a reference. Gateway revalidates the stored approval.
  self.approval_id=reference
 @workflow.run
 async def run(self,request:dict):
  if request['action']['amount_pence']>100000:
   try:await workflow.wait_condition(lambda:self.approval_id is not None,timeout=timedelta(minutes=5))
   except asyncio.TimeoutError:return {'status':'expired','reason':'human approval timed out'}
  return await workflow.execute_activity(commit_action,{'action':request['action'],'approval_id':self.approval_id},
     start_to_close_timeout=timedelta(seconds=45),retry_policy=RetryPolicy(maximum_attempts=3,initial_interval=timedelta(seconds=2)))

async def main():
 from temporalio.client import Client
 from temporalio.worker import Worker
 from .clients import OpenBao
 secret=OpenBao().read('fabric/worker')
 os.environ['AGENT_CLIENT_SECRET']=secret['AGENT_CLIENT_SECRET']
 client=await Client.connect(required('TEMPORAL_ADDRESS'))
 async with Worker(client,task_queue='fabric-credit',workflows=[GovernedCredit],activities=[commit_action]):await asyncio.Event().wait()
if __name__=='__main__':asyncio.run(main())
