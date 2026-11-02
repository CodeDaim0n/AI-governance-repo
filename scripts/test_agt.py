import hashlib,json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1];os.chdir(root);sys.path.insert(0,str(root))
from fabric.core import Fabric
from fabric.microsoft_agt import wrap
from agentmesh.governance import GovernanceDenied
opa=os.environ.get('OPA_BIN','opa')
p=subprocess.Popen([opa,'run','--server','--addr=127.0.0.1:8181','policies/credit.rego'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 for _ in range(50):
  try:
   with urllib.request.urlopen('http://127.0.0.1:8181/health',timeout=.2):break
  except Exception:time.sleep(.1)
 with tempfile.TemporaryDirectory() as tmp:
  f=Fabric(Path(tmp)/'agt.db');f.seed();tool=wrap(f,'agent-a')
  a={'case_id':'case-a','tool':'credit.commit','amount_pence':50000,'idempotency_key':'agt'}
  r=tool(action='credit.commit',proposal=a);assert r['status']=='executed'
  try:tool(action='shell.exec',proposal={**a,'tool':'shell.exec'})
  except GovernanceDenied:pass
  else:raise AssertionError('AGT failed to deny unknown tool')
  r=tool(action='credit.commit',proposal={**a,'case_id':'case-b','idempotency_key':'cross'})
  assert r['status']=='denied' and 'tenant_boundary' in r['reason']
  result={'package':'agent-governance-toolkit-core','version':'5.0.0','tests':3,'passed':3,'cases':['AGT allow followed by OPA allow','AGT default deny unknown tool','AGT allow followed by independent OPA tenant denial'],'scope':'govern wrapper only; no identity mesh, sandbox or performance validation'}
  Path('results/agt.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
finally:p.terminate();p.wait(timeout=5)
