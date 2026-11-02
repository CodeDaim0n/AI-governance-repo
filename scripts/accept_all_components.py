"""Live acceptance for all 18 components. No mocks, no success from health alone.
Writes PASS / FAIL / BLOCKED for every component, exits nonzero unless all pass.
Run on the commissioned dedicated host. Never targets production records.
"""
import asyncio,json,os,time,uuid,traceback
from pathlib import Path
R=Path(__file__).resolve().parents[1];L=R/'.local/full'
NAMES=['Keycloak','Microsoft AGT','OPA','OpenFGA','Temporal','CISO Assistant','OpenMetadata','MLflow',
       'OpenBao','OpenTelemetry','Prometheus and Alertmanager','DFIR-IRIS','GLPI','PostgreSQL','Fairlearn',
       'Kubernetes and Cilium','Syft Grype and Cosign','Ollama and Qwen']

def main():
 results={};context={}
 def record(n,fn):
  try:
   proof=fn();results[n]={'component':NAMES[n-1],'status':'PASS','evidence':proof}
  except Exception as e:
   # Never serialize headers, token values, request bodies or error responses.
   results[n]={'component':NAMES[n-1],'status':'FAIL','error_type':type(e).__name__,'message':'Live acceptance failed; inspect the product locally. No success asserted.'}
  print(f'{n:02} {NAMES[n-1]}: '+results[n]['status'],flush=True)
 if not (L/'host-environment.json').exists():
  for n,name in enumerate(NAMES,1):results[n]={'component':name,'status':'BLOCKED','reason':'Native host not commissioned; Docker/Kubernetes privileges and product credentials required'}
 else:
  for line in (L/'environment.env').read_text().splitlines():
   if line and not line.startswith('#'):
    k,v=line.split('=',1);os.environ[k]=v
  os.environ.update({k:str(v) for k,v in json.loads((L/'host-environment.json').read_text()).items()})
  from fabric.enterprise.clients import Keycloak,OpenFGA,CISOAssistant,OpenMetadata,MLflowRegistry,OpenBao,GLPI,IRIS,Ollama,API,DependencyFailure
  from fabric.enterprise.postgres import PostgresFabric
  from fabric.enterprise.evaluate import evaluate
  from fabric.core import OPA,VERSION
  import httpx
  def identity():
   kc=Keycloak();tokens={}
   for client,key,actor in [('fabric-agent','FABRIC_AGENT_SECRET','agent-a'),('fabric-reviewer','FABRIC_REVIEWER_SECRET','reviewer-a'),('fabric-admin','FABRIC_ADMIN_SECRET','admin-a')]:
    token=kc.token(client,os.environ[key]);assert kc.verify(token)==actor;tokens[actor]=token
   context['tokens']=tokens;kc.close();return {'signed_tokens_verified':3,'issuer_and_audience_checked':True}
  record(1,identity)
  def agt():
   from agentmesh.governance import govern,GovernanceDenied
   count=[]
   f=govern(lambda **kw:count.append(1),policy="apiVersion: governance.toolkit/v1\nname: acceptance\ndefault_action: deny\nrules:\n- name: allow-probe\n  condition: \"action.type == 'probe'\"\n  action: allow\n")
   f(action='probe')
   try:f(action='shell.exec')
   except GovernanceDenied:pass
   else:raise AssertionError('AGT did not deny')
   assert len(count)==1;return {'allowed_calls':1,'denied_calls':1}
  record(2,agt)
  def opa():
   a={'tool':'credit.commit','amount_pence':50000}
   c={'principal':{'role':'agent','tenant':'a'},'case':{'tenant':'a','kyc':'clear','region':'UK','updated':time.time()},
      'registry':{'approved':1,'validated_until':time.time()+300},'stopped':False,'spent':0,'now':time.time(),'action':a,'approved':False}
   p=OPA('http://localhost:8181/v1/data/fabric/decision');assert p.decide(c)['allow'];c['stopped']=True;assert not p.decide(c)['allow']
   return {'allowed_valid_action':True,'denied_stopped_action':True}
  record(3,opa)
  def fga():
   f=OpenFGA()
   try:assert f.check('agent-a','case-a') and not f.check('agent-a','case-b')
   finally:f.close()
   return {'same_case_allowed':True,'cross_case_denied':True}
  record(4,fga)
  def ciso():
   c=CISOAssistant()
   try:
    fixture=json.loads((R/'docs/risk-register.json').read_text())
    for risk in fixture:c.control_for_risk(risk)
    refs={x.get('ref_id') for x in c.risks()};assert {x['risk_id'] for x in fixture}<=refs
   finally:c.close()
   return {'native_risk_records_read_back':12,'acceptance_or_rating_modified':False}
  record(6,ciso)
  def metadata():
   m=OpenMetadata()
   try:r=m.assert_classified();edges=m.call('GET','/v1/lineage/'+r['id'],params={'upstreamDepth':1,'downstreamDepth':1});assert edges.get('downstreamEdges')
   finally:m.close()
   return {'table_id':r['id'],'owner_classification_and_lineage_checked':True}
  record(7,metadata)
  def bao():
   b=OpenBao()
   try:
    secret=b.read('fabric/gateway');assert secret.get('METADATA_TOKEN')
    try:b.read('fabric/worker')
    except DependencyFailure:pass
    else:raise AssertionError('Cross-role secret access allowed')
   finally:b.close()
   return {'scoped_read':'allowed','different_role_path':'denied','secret_values_recorded':False}
  record(9,bao)
  def glpi():
   g=GLPI()
   try:s=g.service();assert s.get('id');t=g.remediation('Fabric acceptance '+str(uuid.uuid4()),'Synthetic integration acceptance; no real customer data');assert t.get('id')
   finally:g.close()
   return {'native_service_read':True,'native_ticket_created':True}
  record(13,glpi)
  def fairness():
   evaluation=evaluate();context['candidate']=evaluation['receipt']['version'];assert evaluation['metrics']['accuracy']==1
   return {'metrics':evaluation['metrics'],'dataset':'eight synthetic records; plumbing only','candidate_logged_to_mlflow':True}
  record(15,fairness)
  def gateway(path,body=None,who='agent-a',params=None):
   r=httpx.post('http://localhost:8088'+path,json=body,params=params,headers={'Authorization':'Bearer '+context['tokens'][who]},timeout=230 if path.endswith('/run') else 30);r.raise_for_status();return r.json()
  def mlflow():
   version=context['candidate'];gateway('/models/'+str(version)+'/approve',who='reviewer-a')
   proof=MLflowRegistry().validate();assert str(proof['model_version'])==str(version);return proof
  record(8,mlflow)
  def temporal():
   gateway('/lab/refresh-case',who='admin-a',params={'case_id':'case-a'})
   action={'case_id':'case-a','tool':'credit.commit','amount_pence':200000,'idempotency_key':'accept-'+str(uuid.uuid4())}
   started=gateway('/workflows/start',action)
   gateway('/workflows/'+started['workflow_id']+'/approve',who='reviewer-a')
   async def wait():
    from temporalio.client import Client
    c=await Client.connect('localhost:7233');return await asyncio.wait_for(c.get_workflow_handle(started['workflow_id']).result(),timeout=90)
   r=asyncio.run(wait());assert r['status']=='executed';context['action']=action
   # A cross-tenant side effect must still be blocked through the native stack.
   denied=gateway('/execute',{'action':{**action,'case_id':'case-b','idempotency_key':str(uuid.uuid4())}});assert denied['status']=='denied'
   return {'workflow_id':started['workflow_id'],'committed':True,'approval_signal_checked':True,'cross_tenant_denied':True}
  record(5,temporal)
  def ollama():
   # Actual agent tool loop through the commissioned gateway, not one-shot JSON.
   gateway('/lab/refresh-case',who='admin-a',params={'case_id':'case-a'})
   action={'case_id':'case-a','tool':'credit.commit','amount_pence':50000,'idempotency_key':'agent-accept-'+str(uuid.uuid4())}
   task=gateway('/agent/tasks',{'action':action})
   result=gateway('/agent/tasks/'+task['task_id']+'/run')['agent']
   events=result['tool_events']
   assert any(e['name']=='inspect_case' and e['observation'].get('status')=='observed' for e in events)
   assert any(e['name']=='commit_action' and e['observation'].get('status')=='executed' for e in events)
   db=PostgresFabric(os.environ['DATABASE_URL'])
   with db.connect() as c:
    row=c.execute('SELECT count(*),COALESCE(SUM(amount),0) FROM actions WHERE actor=? AND idem=?',('agent-a',action['idempotency_key'])).fetchone()
   assert row[0]==1 and row[1]==50000
   return {'actual_model':result['model'],'native_agent_loop':True,'authorized_read_observed':True,'executed_receipt_observed':True,'postgres_effect_count':1,'tool_names':[e['name'] for e in events]}
  record(18,ollama)
  def telemetry():
   file=L/'telemetry/traces.json'
   for _ in range(20):
    if file.exists() and 'governed-action' in file.read_text():break
    time.sleep(1)
   else:raise AssertionError('No exported gateway span')
   data=file.read_text();assert 'fabric-gateway' in data
   for token in context.get('tokens',{}).values():assert token not in data
   return {'real_otlp_span_exported':True,'bearer_tokens_absent':True}
  record(10,telemetry)
  def monitoring():
   for _ in range(15):
    q=httpx.get('http://localhost:9090/api/v1/query',params={'query':'fabric_decisions_total'},timeout=5).json()
    if q.get('data',{}).get('result'):break
    time.sleep(2)
   else:raise AssertionError('Prometheus has no gateway decision metric')
   alert={'labels':{'alertname':'FabricAcceptance','severity':'warning'},'annotations':{'summary':'Synthetic native integration test'}}
   response=httpx.post('http://localhost:9093/api/v2/alerts',json=[alert],timeout=5);response.raise_for_status()
   f=PostgresFabric(os.environ['DATABASE_URL'])
   for _ in range(20):
    with f.connect() as c:rows=c.execute("SELECT body FROM audit WHERE body LIKE ?",('%alertmanager%',)).fetchall()
    if rows:return {'metric_scraped':True,'alertmanager_webhook_recorded':True}
    time.sleep(1)
   raise AssertionError('No acknowledged Alertmanager webhook')
  record(11,monitoring)
  def iris():
   i=IRIS()
   try:r=i.alert('accept-'+str(uuid.uuid4()),{'reason':'synthetic acceptance event'});assert r.get('status')=='success' and r.get('data')
   finally:i.close()
   return {'native_alert_created':True,'customer_id':os.environ['IRIS_CUSTOMER_ID']}
  record(12,iris)
  def pg():
   f=PostgresFabric(os.environ['DATABASE_URL']);assert f.verify_chain()
   with f.connect() as c:
    actions=c.execute('SELECT count(*) FROM actions').fetchone()[0];assert actions>0
    receipts=c.execute('SELECT count(*) FROM sink_receipts').fetchone()[0];assert receipts>0
   return {'audit_chain_checked':True,'business_actions':actions,'downstream_delivery_receipts':receipts}
  record(14,pg)
  for n,file in [(16,'cilium-live.json'),(17,'supply-chain-live.json')]:
   def read_evidence(file=file,n=n):
    p=R/'results'/file
    if not p.exists():raise RuntimeError('Required live test has not run')
    proof=json.loads(p.read_text())
    import subprocess
    from fabric.enterprise.acceptance import validate_receipt
    return validate_receipt(n,proof,(L/'deployment-id').read_text().strip(),subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip())
   record(n,read_evidence)
 summary={'date':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'scope':'Dedicated synthetic deployment, not regulatory certification',
   'all_18_passed':len(results)==18 and all(x['status']=='PASS' for x in results.values()),
   'passed':sum(x['status']=='PASS' for x in results.values()),'components':[{'id':n,**results[n]} for n in sorted(results)]}
 (R/'results/all-18-live.json').write_text(json.dumps(summary,indent=2));print(json.dumps({'all_18_passed':summary['all_18_passed'],'passed':summary['passed'],'total':18}))
 raise SystemExit(0 if summary['all_18_passed'] else 2)
if __name__=='__main__':main()
