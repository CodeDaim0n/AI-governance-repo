"""Create a dedicated kind/Cilium sandbox and verify a policy actually blocks
previously reachable traffic. Never modifies an existing enterprise cluster.
"""
import json,os,subprocess,sys
from pathlib import Path
import yaml
R=Path(__file__).resolve().parents[1];L=R/'.local/full';name='fabric-governance'
def run(*args,**kw):return subprocess.run(list(args),check=True,**kw)
def output(*args):return subprocess.check_output(list(args),text=True).strip()
def kube(*args,**kw):return run('kubectl','--context','kind-'+name,*args,**kw)
def apply(obj):kube('apply','-f','-',input=json.dumps(obj),text=True)
def main():
 clusters=output('kind','get','clusters').splitlines()
 if name not in clusters:run('kind','create','cluster','--name',name,'--config',str(R/'deploy/kubernetes/kind.yaml'))
 run('helm','repo','add','cilium','https://helm.cilium.io/')
 run('helm','upgrade','--install','cilium','cilium/cilium','--version','1.20.4','--namespace','kube-system',
     '--kube-context','kind-'+name,'--set','ipam.mode=kubernetes','--set','operator.replicas=1','--wait','--timeout','5m')
 bridge=json.loads(output('docker','network','inspect','kind'))[0]['IPAM']['Config'][0]['Gateway']
 values={}
 for line in (L/'environment.env').read_text().splitlines():
  if line and not line.startswith('#'):
   k,v=line.split('=',1);values[k]=v
 # Export ONLY gateway and identity onto this private Docker bridge. All vendor
 # interfaces, the database and secret store retain loopback-only host bindings.
 override={'services':{'gateway':{'ports':[f'{bridge}:8088:8088']},'keycloak':{'ports':[f'{bridge}:8081:8080']}}}
 (L/'sandbox-bridge.json').write_text(json.dumps(override))
 run('docker','compose','--env-file',str(L/'environment.env'),'-f',str(R/'deploy/full/compose.yaml'),'-f',str(L/'sandbox-bridge.json'),'up','-d','gateway','keycloak')
 apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':'fabric-lab'}})
 apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'agent-identity','namespace':'fabric-lab'},'type':'Opaque','stringData':{'client_secret':values['FABRIC_AGENT_SECRET']}})
 for pod,labels,command in [('agent',{'app':'fabric-agent'},['python','-c','import time; time.sleep(86400)']),
                            ('negative-target',{'app':'negative-target'},['python','-m','http.server','8080'])]:
  apply({'apiVersion':'v1','kind':'Pod','metadata':{'name':pod,'namespace':'fabric-lab','labels':labels},'spec':{
   'automountServiceAccountToken':False,'hostAliases':[{'ip':bridge,'hostnames':['fabric-host']}],
   'securityContext':{'runAsNonRoot':True,'runAsUser':10001,'seccompProfile':{'type':'RuntimeDefault'}},
   'containers':[{'name':pod,'image':'python:3.12-slim','command':command,
      'env':[{'name':'CLIENT_SECRET','valueFrom':{'secretKeyRef':{'name':'agent-identity','key':'client_secret'}}}] if pod=='agent' else [],
      'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}}}]}})
 kube('-n','fabric-lab','wait','--for=condition=Ready','pod/agent','pod/negative-target','--timeout=120s')
 kube('-n','fabric-lab','delete','ciliumnetworkpolicy','agent-boundary','--ignore-not-found')
 ip=output('kubectl','--context','kind-'+name,'-n','fabric-lab','get','pod','negative-target','-o','jsonpath={.status.podIP}')
 probe="import urllib.request;urllib.request.urlopen('http://"+ip+":8080',timeout=3).read()"
 kube('-n','fabric-lab','exec','agent','--','python','-c',probe)
 policy={'apiVersion':'cilium.io/v2','kind':'CiliumNetworkPolicy','metadata':{'name':'agent-boundary','namespace':'fabric-lab'},'spec':{
  'endpointSelector':{'matchLabels':{'app':'fabric-agent'}},'ingress':[],
  'egress':[{'toCIDR':[bridge+'/32'],'toPorts':[{'ports':[{'port':'8088','protocol':'TCP'},{'port':'8081','protocol':'TCP'}]}]},
   {'toEndpoints':[{'matchLabels':{'k8s:io.kubernetes.pod.namespace':'kube-system','k8s:k8s-app':'kube-dns'}}],
    'toPorts':[{'ports':[{'port':'53','protocol':'UDP'},{'port':'53','protocol':'TCP'}]}]}]}}
 apply(policy)
 # Wait for the agent endpoint policy to converge, then verify both directions.
 kube('-n','kube-system','rollout','status','daemonset/cilium','--timeout=120s')
 blocked=False
 import time
 for _ in range(20):
  test=subprocess.run(['kubectl','--context','kind-'+name,'-n','fabric-lab','exec','agent','--','python','-c',probe],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  if test.returncode:blocked=True;break
  time.sleep(1)
 if not blocked:raise RuntimeError('Cilium failed to block the previously reachable target')
 kube('-n','fabric-lab','exec','agent','--','python','-c',"import urllib.request;urllib.request.urlopen('http://fabric-host:8088/health',timeout=5).read()")
 receipt={'deployment_id':(L/'deployment-id').read_text().strip(),'source_commit':output('git','-C',str(R),'rev-parse','HEAD'),'component':'16 Kubernetes and Cilium','before_policy':'target reachable','after_policy':'target blocked','gateway':'reachable','cluster':name}
 (R/'results/cilium-live.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
if __name__=='__main__':main()
