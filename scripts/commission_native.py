"""Commission dedicated lab APIs. Fail if native credentials/owner IDs are absent.
No guessed identities, disabled TLS checks or fabricated completion statuses.
"""
import json,os,time
from pathlib import Path
from fabric.enterprise.clients import *
from fabric.enterprise.postgres import PostgresFabric
R=Path(__file__).resolve().parents[1];L=R/'.local/full';ENV=L/'environment.env'
def save_env(values):
 current={}
 for line in ENV.read_text().splitlines():
  if line and not line.startswith('#'):
   k,v=line.split('=',1);current[k]=v
 current.update(values);ENV.write_text('\n'.join(k+'='+str(v) for k,v in current.items())+'\n');ENV.chmod(0o600)
 os.environ.update({k:str(v) for k,v in values.items()})
def main():
 for line in ENV.read_text().splitlines():
  if line and not line.startswith('#'):
   k,v=line.split('=',1);os.environ[k]=v
 # Operator provisions scoped native tokens and an authorized metadata owner.
 credentials=json.loads((L/'native-credentials.json').read_text())
 needed=['CISO_TOKEN','CISO_FOLDER_ID','CISO_ASSESSMENT_ID','METADATA_TOKEN','METADATA_OWNER_ID','IRIS_TOKEN','GLPI_APP_TOKEN','GLPI_USER_TOKEN']
 missing=[x for x in needed if not credentials.get(x)]
 if missing:raise SystemExit('Missing native product configuration: '+', '.join(missing))
 os.environ.update({k:str(v) for k,v in credentials.items()})
 password=os.environ['POSTGRES_PASSWORD']
 local={'DATABASE_URL':f'postgresql://fabric:{password}@127.0.0.1:5433/fabric',
 'KEYCLOAK_URL':'http://localhost:8081','KEYCLOAK_ISSUER':'http://localhost:8081/realms/fabric','KEYCLOAK_REALM':'fabric',
 'FGA_URL':'http://localhost:8082','CISO_URL':'http://localhost:8002/api','METADATA_URL':'http://localhost:8585/api',
 'BAO_URL':'http://localhost:8200','IRIS_URL':'http://localhost:8085','IRIS_CUSTOMER_ID':str(credentials.get('IRIS_CUSTOMER_ID','1')),
 'GLPI_URL':'http://localhost:8086/apirest.php','GLPI_ENTITY_ID':'0','OLLAMA_URL':'http://localhost:11434',
 'OLLAMA_MODEL':'qwen3:4b-instruct','MLFLOW_URL':'http://localhost:5001','MODEL_NAME':'fabric-credit-proposal','MODEL_TENANT':'bank-a',
 'METADATA_TABLE_FQN':'fabric.credit.public.cases','METADATA_REQUIRED_TAG':'PII.Sensitive','FAIRNESS_MAX_DIFFERENCE':'0.2'}
 os.environ.update(local)
 # Initialize and unseal OpenBao only on a fresh dedicated installation.
 import httpx
 with httpx.Client(timeout=10) as h:
  init=h.get(local['BAO_URL']+'/v1/sys/init').json()
  state=L/'bao-init.json'
  if not init['initialized']:
   result=h.post(local['BAO_URL']+'/v1/sys/init',json={'secret_shares':1,'secret_threshold':1});result.raise_for_status()
   fd=os.open(state,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   with os.fdopen(fd,'w') as f:json.dump(result.json(),f)
  if not state.exists():raise SystemExit('Initialized Bao has no local commissioning record; use approved unseal procedure')
  keys=json.loads(state.read_text());resp=h.post(local['BAO_URL']+'/v1/sys/unseal',json={'key':keys['keys'][0]});resp.raise_for_status()
  headers={'X-Vault-Token':keys['root_token']}
  mounts=h.get(local['BAO_URL']+'/v1/sys/mounts',headers=headers);mounts.raise_for_status()
  if 'secret/' not in mounts.json()['data']:
   q=h.post(local['BAO_URL']+'/v1/sys/mounts/secret',headers=headers,json={'type':'kv','options':{'version':'2'}});q.raise_for_status()
  secret={k:credentials[k] for k in ['CISO_TOKEN','METADATA_TOKEN','IRIS_TOKEN','GLPI_APP_TOKEN','GLPI_USER_TOKEN']}
  secret.update({'AGENT_CLIENT_SECRET':os.environ['FABRIC_AGENT_SECRET'],'ALERT_WEBHOOK_TOKEN':os.environ['ALERT_WEBHOOK_TOKEN']})
  role_secrets={
   'gateway':{k:secret[k] for k in ['METADATA_TOKEN','GLPI_APP_TOKEN','GLPI_USER_TOKEN','ALERT_WEBHOOK_TOKEN']},
   'worker':{'AGENT_CLIENT_SECRET':secret['AGENT_CLIENT_SECRET']},
   'dispatch':{k:secret[k] for k in ['CISO_TOKEN','IRIS_TOKEN','GLPI_APP_TOKEN','GLPI_USER_TOKEN']}}
  bao_tokens={}
  for role,role_secret in role_secrets.items():
   path='fabric/'+role
   q=h.post(local['BAO_URL']+'/v1/secret/data/'+path,headers=headers,json={'data':role_secret});q.raise_for_status()
   policy='path "secret/data/'+path+'" { capabilities = ["read"] }'
   q=h.put(local['BAO_URL']+'/v1/sys/policies/acl/fabric-'+role,headers=headers,json={'policy':policy});q.raise_for_status()
   q=h.post(local['BAO_URL']+'/v1/auth/token/create',headers=headers,json={'policies':['fabric-'+role],'ttl':'24h','renewable':True});q.raise_for_status()
   bao_tokens[role]=q.json()['auth']['client_token']
 values={'BAO_TOKEN':bao_tokens['gateway'],'BAO_WORKER_TOKEN':bao_tokens['worker'],'BAO_DISPATCH_TOKEN':bao_tokens['dispatch'],**{k:credentials[k] for k in ['CISO_FOLDER_ID','CISO_ASSESSMENT_ID']}}
 if not os.environ.get('FGA_STORE_ID'):values.update(OpenFGA().bootstrap())
 save_env(values)
 f=PostgresFabric(local['DATABASE_URL']);f.seed()
 # Real risk-register creation, with no autonomous ratings or acceptance changes.
 ciso=CISOAssistant()
 try:
  for risk in json.loads((R/'docs/risk-register.json').read_text()):ciso.control_for_risk(risk)
 finally:ciso.close()
 glpi=GLPI()
 try:
  if not credentials.get('GLPI_SERVICE_ID'):
   service=glpi.call('POST','/Computer',{'input':{'name':'Fabric synthetic credit service','entities_id':int(local['GLPI_ENTITY_ID'])}})
   values['GLPI_SERVICE_ID']=str(service['id'])
  else:values['GLPI_SERVICE_ID']=str(credentials['GLPI_SERVICE_ID'])
 finally:glpi.close()
 # Create real metadata entities and lineage; no source database password stored.
 om=OpenMetadata();owner={'id':credentials['METADATA_OWNER_ID'],'type':'user'}
 try:
  om.call('PUT','/v1/services/databaseServices',{'name':'fabric','serviceType':'CustomDatabase','connection':{'config':{'type':'CustomDatabase'}}})
  om.call('PUT','/v1/databases',{'name':'credit','service':'fabric'})
  om.call('PUT','/v1/databaseSchemas',{'name':'public','database':'fabric.credit'})
  tables=[]
  for name in ['cases','commitments']:
   tables.append(om.call('PUT','/v1/tables',{'name':name,'databaseSchema':'fabric.credit.public','owners':[owner],
     'columns':[{'name':'case_id','dataType':'STRING'}],
     'tags':[{'tagFQN':'PII.Sensitive','labelType':'Manual','state':'Confirmed','source':'Classification'}]}))
  om.lineage(tables[0]['id'],tables[1]['id']);om.assert_classified()
 finally:om.close()
 save_env(values)
 with httpx.Client(timeout=900) as h:
  q=h.post(local['OLLAMA_URL']+'/api/pull',json={'name':local['OLLAMA_MODEL'],'stream':False});q.raise_for_status()
 from fabric.enterprise.evaluate import evaluate
 report=evaluate();(L/'evaluation.json').write_text(json.dumps(report,indent=2))
 (L/'host-environment.json').write_text(json.dumps({**local,**credentials,**values},indent=2));(L/'host-environment.json').chmod(0o600)
 if not (L/'deployment-id').exists():
  import uuid
  (L/'deployment-id').write_text(str(uuid.uuid4()))
 print('Native commissioning completed. Candidate model still requires reviewer approval through /models/{version}/approve. Root/unseal material is lab-only and must be secured offline.')
if __name__=='__main__':main()
