"""Finite, explicit deployment phases for a dedicated synthetic Linux host.
Never starts a partial stack and calls it all 18. No cloud resources provisioned.
"""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];L=R/'.local/full';ENV=L/'environment.env'
VENDORS={
 'ciso':('https://github.com/intuitem/ciso-assistant-community.git','v4.2.1','docker-compose.yml'),
 'iris':('https://github.com/dfir-iris/iris-web.git','v2.4.29','docker-compose.yml'),
 'metadata':('https://github.com/open-metadata/OpenMetadata.git','2.0.7-release','docker/docker-compose-quickstart/docker-compose.yml'),
 'glpi':('https://github.com/glpi-project/docker-images.git','main','docker-compose.example.yml')}
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def core(*args):return run(['docker','compose','--env-file',str(ENV),'-f',str(R/'deploy/full/compose.yaml'),*args],cwd=R)
def preflight():
 errors=[]
 for tool in ['docker','git','kind','kubectl','helm','syft','grype','cosign']:
  if not shutil.which(tool):errors.append('missing executable: '+tool)
 if shutil.which('docker'):
  p=subprocess.run(['docker','info'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  if p.returncode:errors.append('Docker daemon unavailable')
 if not ENV.exists():errors.append('private configuration missing: run configure_full.py')
 print(json.dumps({'ready':not errors,'blockers':errors,'host_requirement':'Dedicated Linux host; 32 GiB RAM and 80 GiB free disk recommended; Docker privileges and kernel eBPF support required','no_services_started':True},indent=2))
 return not errors

def vendors():
 import yaml
 lock={}
 for name,(url,ref,relative) in VENDORS.items():
  dest=L/'vendors'/name
  if not dest.exists():run(['git','clone','--depth','1','--branch',ref,url,str(dest)],stdout=subprocess.DEVNULL)
  sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=dest,text=True).strip()
  lock[name]={'url':url,'requested_ref':ref,'resolved_commit':sha,'compose':relative}
  # Resolve official Compose extends/environment before applying loopback-only
  # host bindings. Avoid maintaining a fork of the vendor's service topology.
  if name=='iris':
   env=dest/'.env'
   if not env.exists():
    import secrets
    data=(dest/'.env.model').read_text()
    for key in ['POSTGRES_PASSWORD','POSTGRES_ADMIN_PASSWORD','IRIS_SECRET_KEY','IRIS_SECURITY_PASSWORD_SALT']:
     import re
     data=re.sub(r'^'+key+r'=.*$',key+'='+secrets.token_urlsafe(32),data,flags=re.M)
    data=data.replace('=latest','=v2.4.29')
    data+='\nIRIS_ADM_API_KEY='+os.environ.get('IRIS_TOKEN','')+'\n'
    env.write_text(data);env.chmod(0o600)
  if name=='glpi' and not (dest/'.env').exists() and (dest/'.env.example').exists():
   shutil.copyfile(dest/'.env.example',dest/'.env');(dest/'.env').chmod(0o600)
  raw=subprocess.check_output(['docker','compose','-f',str(dest/relative),'config','--format','json'],cwd=(dest/relative).parent,text=True)
  config=json.loads(raw)
  for service in config.get('services',{}).values():
   service.pop('container_name',None)
   for port in service.get('ports',[]):
    if isinstance(port,dict):port['host_ip']='127.0.0.1'
   if name=='ciso' and str(service.get('image','')).startswith('ghcr.io/intuitem/'):
    service['image']=service['image'].replace(':latest',':v4.2.1')
  # Explicit extra loopback API ports for native bridges.
  if name=='ciso':config['services']['backend'].setdefault('ports',[]).append({'target':8000,'published':'8002','host_ip':'127.0.0.1','protocol':'tcp'})
  if name=='iris':config['services']['app'].setdefault('ports',[]).append({'target':8000,'published':'8085','host_ip':'127.0.0.1','protocol':'tcp'})
  if name=='glpi':
   web=next((s for n,s in config['services'].items() if 'glpi' in n),None)
   if web is None:raise RuntimeError('Official GLPI Compose service changed: review descriptor')
   web['ports']=[{'target':80,'published':'8086','host_ip':'127.0.0.1','protocol':'tcp'}]
  path=L/(name+'-compose.json');path.write_text(json.dumps(config,indent=2));path.chmod(0o600)
 (L/'vendor-lock.json').write_text(json.dumps(lock,indent=2))
 print('Vendor descriptors resolved to commits. Configuration contains secrets; kept private.')

def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['preflight','vendors','up-core','up-vendors','up-app','status','stop']);a=p.parse_args()
 if a.phase=='preflight':raise SystemExit(0 if preflight() else 2)
 if not ENV.exists():raise SystemExit('Run configure_full.py first')
 # Load only generated uppercase key=value data. Never execute a shell env file.
 for line in ENV.read_text().splitlines():
  if line and not line.startswith('#'):
   k,v=line.split('=',1);os.environ[k]=v
 if a.phase=='vendors':vendors()
 elif a.phase=='up-core':core('up','-d','--build','postgres','keycloak','opa','fga-migrate','openfga','temporal','mlflow','bao','otel','prometheus','alertmanager','ollama')
 elif a.phase=='up-vendors':
  for name in VENDORS:run(['docker','compose','-p','fabric-'+name,'-f',str(L/(name+'-compose.json')),'up','-d'])
 elif a.phase=='up-app':core('up','-d','--build','gateway','worker','dispatch')
 elif a.phase=='status':core('ps')
 elif a.phase=='stop':
  # Recoverable stop; never delete volumes or evidence.
  core('stop')
  for name in VENDORS:
   if (L/(name+'-compose.json')).exists():run(['docker','compose','-p','fabric-'+name,'-f',str(L/(name+'-compose.json')),'stop'])
if __name__=='__main__':main()
