"""Native-stack API. Trusted product calls, AGT interception and PG evidence."""
import asyncio,json,os,uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI,Header,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,ConfigDict,StrictInt,StrictStr
from fabric.core import Rejected,canonical
from fabric.microsoft_agt import wrap
from agentmesh.governance import GovernanceDenied
from .clients import Keycloak,OpenBao,required,DependencyFailure,MLflowRegistry,Ollama
from .postgres import PostgresFabric
from .policy import EnterprisePolicy
from .telemetry import setup,DECISIONS,DEPENDENCIES,generate_latest

class Action(BaseModel):
 model_config=ConfigDict(extra='forbid')
 case_id:StrictStr;tool:StrictStr;amount_pence:StrictInt;idempotency_key:StrictStr
class Execute(BaseModel):
 model_config=ConfigDict(extra='forbid')
 action:Action;approval_id:str|None=None
class Approve(BaseModel):
 model_config=ConfigDict(extra='forbid')
 action:Action;actor:StrictStr

@asynccontextmanager
async def lifespan(app):
 # URLs are administrator-controlled configuration. Only secret values come
 # from Bao; no arbitrary environment-variable injection from secret records.
 secrets=OpenBao().read('fabric/gateway')
 for name in ['CISO_TOKEN','IRIS_TOKEN','GLPI_APP_TOKEN','GLPI_USER_TOKEN','METADATA_TOKEN',
              'AGENT_CLIENT_SECRET','ALERT_WEBHOOK_TOKEN']:
  if name in secrets:os.environ[name]=secrets[name]
 app.state.identity=Keycloak();app.state.tracer=setup()
 app.state.fabric=PostgresFabric(required('DATABASE_URL'),EnterprisePolicy(required('OPA_DECISION_URL')))
 with app.state.fabric.tx() as c:
  c.execute('CREATE TABLE IF NOT EXISTS workflow_requests(id TEXT PRIMARY KEY,actor TEXT,action TEXT)')
  c.execute('CREATE TABLE IF NOT EXISTS agent_tasks(id TEXT PRIMARY KEY,actor TEXT,action TEXT,created DOUBLE PRECISION,expires DOUBLE PRECISION,inspected INT,approval_id TEXT,workflow_id TEXT)')
 yield
 app.state.identity.close()
app=FastAPI(title='Governed Agent Fabric native stack',lifespan=lifespan)

def actor(authorization):
 if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'Bearer token required')
 try:return app.state.identity.verify(authorization[7:])
 except DependencyFailure:raise HTTPException(401,'Invalid identity')

def run_action(who,request):
 f=app.state.fabric
 with f.connect() as c:
  backlog=c.execute('SELECT count(*) FROM outbox WHERE delivered=0').fetchone()[0]
 if backlog>=int(os.environ.get('MAX_OUTBOX_PENDING','1000')):
  raise HTTPException(503,'Evidence backlog limit reached; writes restricted')
 with app.state.tracer.start_as_current_span('governed-action') as span:
  # Deliberately no body, token, customer ID or generated text in spans.
  try:
   result=wrap(f,who)(action=request.action.tool,proposal=request.action.model_dump(),approval_id=request.approval_id)
   DECISIONS.labels(result['status']).inc()
   if 'policy_unavailable' in result.get('reason',''):DEPENDENCIES.inc()
   span.set_attribute('fabric.outcome',result['status'])
   return result
  except Rejected as e:raise HTTPException(403,str(e))
  except GovernanceDenied:raise HTTPException(403,'Tool denied by agent governance policy')
  except Exception:
   DEPENDENCIES.inc();raise HTTPException(503,'Authority or storage dependency unavailable')

@app.get('/health')
def health():return {'status':'alive','note':'Use the live acceptance suite for readiness, not this endpoint.'}
@app.get('/metrics')
def metrics():
 from .telemetry import OUTBOX
 with app.state.fabric.connect() as c:OUTBOX.set(c.execute('SELECT count(*) FROM outbox WHERE delivered=0').fetchone()[0])
 return Response(generate_latest(),media_type='text/plain; version=0.0.4')
@app.post('/execute')
async def execute(request:Execute,authorization:str|None=Header(default=None)):
 who=actor(authorization);return await asyncio.to_thread(run_action,who,request)
@app.post('/approve')
async def approve(request:Approve,authorization:str|None=Header(default=None)):
 who=actor(authorization)
 try:return {'approval_id':await asyncio.to_thread(app.state.fabric.approve,who,request.actor,request.action.model_dump())}
 except Rejected as e:raise HTTPException(403,str(e))
@app.post('/stop')
def stop(stopped:bool,authorization:str|None=Header(default=None)):
 try:app.state.fabric.stop(actor(authorization),stopped);return {'stopped':stopped}
 except Rejected as e:raise HTTPException(403,str(e))
@app.post('/propose')
async def propose(request:Action,authorization:str|None=Header(default=None)):
 who=actor(authorization)
 # The caller supplies bounded intent; the model proposes fields only.
 prompt='Return only JSON with case_id, tool, amount_pence and idempotency_key for this synthetic action: '+canonical(request.model_dump())
 result=await asyncio.to_thread(Ollama().propose,prompt)
 try:proposal=Action.model_validate(result['proposal'])
 except Exception:raise HTTPException(422,'Model proposal failed the action schema')
 # Model output cannot silently change the requested case, amount or operation.
 if proposal.model_dump()!=request.model_dump():raise HTTPException(422,'Model changed the authorized intent')
 return {'proposal':proposal.model_dump(),'model':result['model'],'actor':who}
@app.post('/workflows/start')
async def start_workflow(request:Action,authorization:str|None=Header(default=None)):
 who=actor(authorization)
 if who!='agent-a':raise HTTPException(403,'This lab worker is delegated to agent-a only')
 from temporalio.client import Client
 from .workflows import GovernedCredit
 wid='fabric-'+str(uuid.uuid4())
 with app.state.fabric.tx() as c:c.execute('INSERT INTO workflow_requests VALUES(?,?,?)',(wid,who,canonical(request.model_dump())))
 client=await Client.connect(required('TEMPORAL_ADDRESS'))
 await client.start_workflow(GovernedCredit.run,{'action':request.model_dump()},id=wid,task_queue='fabric-credit')
 return {'workflow_id':wid}
@app.post('/workflows/{workflow_id}/approve')
async def approve_workflow(workflow_id:str,authorization:str|None=Header(default=None)):
 who=actor(authorization)
 with app.state.fabric.connect() as c:row=c.execute('SELECT * FROM workflow_requests WHERE id=?',(workflow_id,)).fetchone()
 if not row:raise HTTPException(404,'Unknown workflow')
 try:aid=await asyncio.to_thread(app.state.fabric.approve,who,row['actor'],json.loads(row['action']))
 except Rejected as e:raise HTTPException(403,str(e))
 from temporalio.client import Client
 client=await Client.connect(required('TEMPORAL_ADDRESS'))
 await client.get_workflow_handle(workflow_id).signal('approval',aid)
 return {'approval_id':aid,'workflow_id':workflow_id}
@app.post('/models/{version}/approve')
def approve_model(version:str,authorization:str|None=Header(default=None)):
 who=actor(authorization)
 with app.state.fabric.tx() as c:
  p=app.state.fabric.principal(c,who)
  if p['role']!='reviewer' or p['tenant']!=required('MODEL_TENANT'):raise HTTPException(403,'Scoped independent reviewer role required')
  reg=MLflowRegistry();m=reg.client.get_model_version(required('MODEL_NAME'),version)
  run=reg.client.get_run(m.run_id)
  from .configuration import enforce_metric_requirements,ConfigurationError
  try:enforce_metric_requirements(run.data.metrics)
  except ConfigurationError:raise HTTPException(403,'Evaluation requirements not satisfied')
  import time
  expiry=time.time()+3600
  reg.client.set_tag(m.run_id,'fabric.independent_approval','true')
  reg.client.set_tag(m.run_id,'fabric.validation_expires',str(expiry))
  reg.client.set_registered_model_alias(required('MODEL_NAME'),'validated',version)
  c.execute('UPDATE registry SET approved=1,version=?,validated_until=? WHERE id=?',(version,expiry,'credit-workflow'))
  app.state.fabric.event(c,{'actor':who,'outcome':'model_approved','model_version':version,'scope':'synthetic lab only'})
 return {'version':version,'approved_for':'synthetic lab only'}
@app.post('/alerts')
def alerts(body:dict,authorization:str|None=Header(default=None)):
 import hmac
 expected='Bearer '+required('ALERT_WEBHOOK_TOKEN')
 if not authorization or not hmac.compare_digest(authorization,expected):raise HTTPException(401,'Invalid alert receiver token')
 with app.state.fabric.tx() as c:
  for alert in body.get('alerts',[])[:20]:
   # No automatic stop from attacker-controlled metric labels.
   app.state.fabric.event(c,{'actor':'alertmanager','outcome':'denied',
     'reason':alert.get('labels',{}).get('alertname','unknown')[:100]})
 return {'accepted':True}

@app.post('/lab/refresh-case')
def lab_refresh(case_id:str,authorization:str|None=Header(default=None)):
 if os.environ.get('FABRIC_LAB_MODE')!='true':raise HTTPException(404,'Unavailable')
 who=actor(authorization)
 with app.state.fabric.tx() as c:
  if app.state.fabric.principal(c,who)['role']!='admin':raise HTTPException(403,'Admin required')
  import time
  c.execute('UPDATE cases SET updated=?,version=version+1 WHERE id=?',(time.time(),case_id))
  app.state.fabric.event(c,{'actor':who,'outcome':'synthetic_case_refreshed','scope':'lab only'})
 return {'refreshed':case_id,'synthetic':True}

# Autonomous tool loop; source/intent boundaries apply independently of prompts.
from .agent_routes import install as install_agent_routes
install_agent_routes(app,actor,run_action,Action,Execute)
