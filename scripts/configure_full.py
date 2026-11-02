"""Generate private lab configuration, never print secrets. Does not deploy."""
import json,os,secrets
from pathlib import Path
import yaml
root=Path(__file__).resolve().parents[1];local=root/'.local/full';local.mkdir(parents=True,exist_ok=True);local.chmod(0o700)
config=local/'environment.env'
if config.exists():raise SystemExit('Private configuration already exists; refusing to overwrite credentials.')
values={k:secrets.token_urlsafe(32) for k in ['POSTGRES_PASSWORD','KEYCLOAK_ADMIN_PASSWORD','FGA_TOKEN','ALERT_WEBHOOK_TOKEN','IRIS_TOKEN']}
values.update({'FABRIC_UID':str(os.getuid()),'FABRIC_GID':str(os.getgid())})
clients=[]
for client,actor in [('fabric-agent','agent-a'),('fabric-other-agent','agent-b'),('fabric-reviewer','reviewer-a'),('fabric-admin','admin-a')]:
 secret=secrets.token_urlsafe(32);values[client.upper().replace('-','_')+'_SECRET']=secret
 clients.append({'clientId':client,'secret':secret,'enabled':True,'publicClient':False,'serviceAccountsEnabled':True,
  'standardFlowEnabled':False,'directAccessGrantsEnabled':False,'fullScopeAllowed':False,'protocol':'openid-connect','protocolMappers':[
   {'name':'audience','protocol':'openid-connect','protocolMapper':'oidc-audience-mapper','config':{'included.custom.audience':'fabric-gateway','access.token.claim':'true'}},
   {'name':'principal','protocol':'openid-connect','protocolMapper':'oidc-hardcoded-claim-mapper','config':{'claim.name':'fabric_principal','claim.value':actor,'jsonType.label':'String','access.token.claim':'true'}}]})
def private(path,data):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:f.write(data)
private(local/'realm.json',json.dumps({'realm':'fabric','enabled':True,'accessTokenLifespan':300,'clients':clients}));(local/'realm.json').chmod(0o444)
private(config,'\n'.join(k+'='+v for k,v in values.items())+'\n')
alert={'route':{'receiver':'fabric','group_wait':'5s','repeat_interval':'5m'},'receivers':[{'name':'fabric','webhook_configs':[{'url':'http://gateway:8088/alerts','http_config':{'authorization':{'type':'Bearer','credentials':values['ALERT_WEBHOOK_TOKEN']}}}]}]}
private(local/'alertmanager.yaml',yaml.safe_dump(alert));(local/'alertmanager.yaml').chmod(0o444)
(local/'telemetry').mkdir(exist_ok=True);(local/'telemetry').chmod(0o700) # Collector container writes minimized synthetic traces only.
print('Created private configuration. No credentials printed. Next: scripts/full_stack.py preflight')
