"""Native APIs with bounded requests. No model-supplied base URLs or secrets."""
import json,os,time,hashlib
from urllib.parse import quote
import httpx
from .configuration import (ConfigurationError, allowed_principals, fga_binding,
    metadata_binding, setting, text_value, finite_number, enforce_metric_requirements)

class DependencyFailure(RuntimeError): pass

def required(name):
    value=os.environ.get(name)
    if not value: raise DependencyFailure('Missing configuration: '+name)
    return value

class API:
    def __init__(self,base,headers=None):
        self.base=base.rstrip('/')
        if not self.base.startswith(('http://','https://')):raise ValueError('invalid service URL')
        self.client=httpx.Client(headers=headers or {},timeout=10,follow_redirects=False,trust_env=False)
    def call(self,method,path,body=None,params=None):
        if not path.startswith('/') or '://' in path:raise ValueError('relative API path required')
        try:
            r=self.client.request(method,self.base+path,json=body,params=params)
            r.raise_for_status()
            return r.json() if r.content else {}
        except (httpx.HTTPError,ValueError) as e:
            # Do not include response bodies or headers: may contain credentials/PII.
            raise DependencyFailure(f'{type(self).__name__} {method} failed') from e
    def pages(self,path,params=None):
        rows=[]
        for _ in range(100):
            result=self.call('GET',path,params=params)
            if isinstance(result,list):return rows+result
            rows.extend(result.get('results',[]))
            nxt=result.get('next')
            if not nxt:return rows
            from urllib.parse import urlsplit
            base=urlsplit(self.base);target=urlsplit(nxt)
            if target.netloc and (target.scheme,target.netloc)!=(base.scheme,base.netloc):
                raise DependencyFailure('Untrusted pagination destination')
            path=target.path
            if path.startswith(base.path):path=path[len(base.path):]
            path=path or '/'
            if target.query:path+='?'+target.query
            params=None
        raise DependencyFailure('Pagination limit exceeded')
    def close(self):self.client.close()

class Keycloak(API):
    def __init__(self):
        allowed_principals()  # Invalid operator mappings fail before authentication.
        super().__init__(required('KEYCLOAK_URL'))
        self.realm=required('KEYCLOAK_REALM')
        self.issuer=required('KEYCLOAK_ISSUER')
        import jwt
        self.jwt=jwt
        self.jwks=jwt.PyJWKClient(self.base+f'/realms/{self.realm}/protocol/openid-connect/certs',cache_keys=True,lifespan=60,timeout=5)
    def verify(self,token):
        try:
            key=self.jwks.get_signing_key_from_jwt(token)
            c=self.jwt.decode(token,key.key,algorithms=['RS256'],audience='fabric-gateway',issuer=self.issuer,
                              options={'require':['exp','iat','sub','iss','aud']})
            # Lab realm maps service accounts to bounded principals. Production
            # must use an immutable enterprise subject mapping, not arbitrary names.
            actor=c.get('fabric_principal')
            if actor not in allowed_principals():raise ValueError('unmapped identity')
            return actor
        except Exception as e:raise DependencyFailure('Identity verification failed') from e
    def token(self,client_id,client_secret):
        try:
            r=self.client.post(self.base+f'/realms/{self.realm}/protocol/openid-connect/token',data={
                'grant_type':'client_credentials','client_id':client_id,'client_secret':client_secret})
            r.raise_for_status();return r.json()['access_token']
        except Exception as e:raise DependencyFailure('Token acquisition failed') from e

class OpenFGA(API):
    def __init__(self):super().__init__(required('FGA_URL'),{'Authorization':'Bearer '+required('FGA_TOKEN')})
    def check(self,actor,case,*,object_type=None,relation=None,user_type=None):
        binding=fga_binding(object_type=object_type,relation=relation,user_type=user_type)
        for label,value in [('actor',actor),('resource',case)]:
            text_value(value,label)
            if '#' in value or '*' in value:raise ConfigurationError('Invalid FGA '+label+' identifier')
        payload={'authorization_model_id':required('FGA_MODEL_ID'),
                 'tuple_key':{'user':binding['user_type']+':'+actor,'relation':binding['relation'],
                              'object':binding['object_type']+':'+case},
                 'consistency':'HIGHER_CONSISTENCY'}
        result=self.call('POST','/stores/'+quote(required('FGA_STORE_ID'),safe='')+'/check',payload)
        if type(result.get('allowed')) is not bool:raise DependencyFailure('Malformed relationship decision')
        return result['allowed']
    def bootstrap(self):
        if fga_binding()!={'user_type':'user','object_type':'case','relation':'operator'}:
            raise ConfigurationError('Lab bootstrap requires default FGA types; provision a scoped model for custom bindings')
        store=self.call('POST','/stores',{'name':'fabric-lab'})['id']
        model={'schema_version':'1.1','type_definitions':[{'type':'user'},{'type':'case','relations':{'operator':{'this':{}}},
               'metadata':{'relations':{'operator':{'directly_related_user_types':[{'type':'user'}]}}}}]}
        mid=self.call('POST',f'/stores/{store}/authorization-models',model)['authorization_model_id']
        self.call('POST',f'/stores/{store}/write',{'authorization_model_id':mid,'writes':{'tuple_keys':[
            {'user':'user:agent-a','relation':'operator','object':'case:case-a'},
            {'user':'user:agent-b','relation':'operator','object':'case:case-b'}]}})
        return {'FGA_STORE_ID':store,'FGA_MODEL_ID':mid}

class CISOAssistant(API):
    def __init__(self):super().__init__(required('CISO_URL'),{'Authorization':'Token '+required('CISO_TOKEN')})
    @staticmethod
    def object_id(value):
        return str(value.get('id','')) if isinstance(value,dict) else str(value or '')
    def risks(self):
        rows=self.pages('/risk-scenarios/',params={'risk_assessment':required('CISO_ASSESSMENT_ID')})
        return [x for x in rows if self.object_id(x.get('risk_assessment'))==required('CISO_ASSESSMENT_ID')]
    def control_name(self,risk_id):
        return 'Fabric '+required('CISO_ASSESSMENT_ID')+' '+risk_id+' control'

    def create_risk(self,risk):
        # Creation only: automated sync never overwrites owner ratings/acceptance.
        existing=[x for x in self.risks() if x.get('ref_id')==risk['risk_id']]
        if existing:return existing[0]
        return self.call('POST','/risk-scenarios/',{'name':risk['title'],'ref_id':risk['risk_id'],
          'description':risk['scenario']+'\nControl: '+risk['control']+'\nAssurance: '+risk['assurance_status'],
          'risk_assessment':required('CISO_ASSESSMENT_ID'),'folder':required('CISO_FOLDER_ID')})
    @staticmethod
    def ids(values):
        return [str(x['id'] if isinstance(x,dict) else x) for x in values]
    def detail(self,collection,record):
        item=self.call('GET','/'+collection+'/'+quote(str(record['id']),safe='')+'/')
        if str(item.get('id'))!=str(record['id']) or self.object_id(item.get('folder'))!=required('CISO_FOLDER_ID'):
            raise DependencyFailure('CISO detail scope mismatch')
        return item
    def control_for_risk(self,risk):
        scenario=self.detail('risk-scenarios',self.create_risk(risk));name=self.control_name(risk['risk_id'])
        if self.object_id(scenario.get('risk_assessment'))!=required('CISO_ASSESSMENT_ID'):
            raise DependencyFailure('CISO detail assessment mismatch')
        controls=[x for x in self.pages('/applied-controls/') if x.get('name')==name and self.object_id(x.get('folder'))==required('CISO_FOLDER_ID')]
        control=controls[0] if controls else self.call('POST','/applied-controls/',{
            'name':name,'description':risk['control'],'folder':required('CISO_FOLDER_ID')})
        linked=self.ids(scenario.get('applied_controls',[]))
        if str(control['id']) not in linked:
            self.call('PATCH','/risk-scenarios/'+str(scenario['id'])+'/',{'applied_controls':linked+[str(control['id'])]})
        return control
    def evidence(self,event_id,record):
        name='Fabric event '+event_id
        existing=[x for x in self.pages('/evidences/') if x.get('name')==name and self.object_id(x.get('folder'))==required('CISO_FOLDER_ID')]
        evidence=existing[0] if existing else self.call('POST','/evidences/',{'name':name,'folder':required('CISO_FOLDER_ID'),
            'description':json.dumps(record,sort_keys=True)})
        # Only attach evidence links. Never overwrite risk ratings or acceptance.
        for rid in record.get('risk_ids',[]):
            controls=[x for x in self.pages('/applied-controls/') if x.get('name')==self.control_name(rid) and self.object_id(x.get('folder'))==required('CISO_FOLDER_ID')]
            for control in controls:
                # List serializers can omit relations. Merge from detail rather
                # than treating a missing summary field as an empty relation set.
                control=self.detail('applied-controls',control)
                linked=self.ids(control.get('evidences',[]))
                if str(evidence['id']) not in linked:
                    self.call('PATCH','/applied-controls/'+str(control['id'])+'/',{'evidences':linked+[str(evidence['id'])]})
        return evidence

class OpenMetadata(API):
    def __init__(self):super().__init__(required('METADATA_URL'),{'Authorization':'Bearer '+required('METADATA_TOKEN')})
    def table(self):
        # Compatibility name for existing callers; the binding selects the entity.
        return self.entity()
    def entity(self,**overrides):
        binding=metadata_binding(**overrides)
        return self.call('GET','/v1/'+binding['entity_collection']+'/name/'+quote(binding['entity_fqn'],safe=''),params={'fields':'tags,owners'})
    def assert_classified(self,*,entity_type=None,entity_collection=None,entity_fqn=None,required_tag=None):
        binding=metadata_binding(entity_type=entity_type,entity_collection=entity_collection,
                                 entity_fqn=entity_fqn,required_tag=required_tag)
        t=self.entity(**binding);tags={x['tagFQN'] for x in t.get('tags',[])}
        if binding['required_tag'] not in tags:raise DependencyFailure('Required classification missing')
        if not t.get('owners'):raise DependencyFailure('Data owner missing')
        return {'id':t['id'],'version':t.get('version'),'updatedAt':t.get('updatedAt')}
    def lineage(self,source_id,target_id):
        entity_type=setting('METADATA_ENTITY_TYPE','table',api_identifier=True)
        return self.call('PUT','/v1/lineage',{'edge':{'fromEntity':{'id':source_id,'type':entity_type},
            'toEntity':{'id':target_id,'type':entity_type}}})

class MLflowRegistry:
    def __init__(self):
        os.environ.setdefault('MLFLOW_HTTP_REQUEST_TIMEOUT','5')
        os.environ.setdefault('MLFLOW_HTTP_REQUEST_MAX_RETRIES','0')
        from mlflow import MlflowClient
        self.client=MlflowClient(tracking_uri=required('MLFLOW_URL'))
    def validate(self,*,model_name=None,metric_requirements=None):
        name=setting('MODEL_NAME',override=model_name)
        m=self.client.get_model_version_by_alias(name,'validated')
        run=self.client.get_run(m.run_id)
        try:expiry=finite_number(float(run.data.tags.get('fabric.validation_expires','0')),'Validation expiry')
        except (ValueError,TypeError,OverflowError) as e:raise DependencyFailure('Invalid model validation expiry') from e
        if expiry<=time.time():raise DependencyFailure('Model validation expired')
        if run.data.tags.get('fabric.independent_approval')!='true':raise DependencyFailure('Model release lacks approval')
        try:enforce_metric_requirements(run.data.metrics,metric_requirements)
        except ConfigurationError as e:raise DependencyFailure('Model evaluation requirements not met') from e
        return {'model_version':m.version,'run_id':m.run_id,'expires':expiry}
    def publish_evaluation(self,metrics,artifact):
        import mlflow
        mlflow.set_tracking_uri(required('MLFLOW_URL'));mlflow.set_experiment('fabric-validation')
        with mlflow.start_run() as run:
            mlflow.log_metrics(metrics);mlflow.set_tags({'fabric.validation_expires':str(time.time()+3600),
                'fabric.independent_approval':'false','fabric.dataset':artifact['dataset'],
                'fabric.dataset_origin':artifact.get('dataset_origin','unspecified')})
            mlflow.log_dict(artifact,'evaluation.json');runid=run.info.run_id
        name=required('MODEL_NAME')
        try:self.client.get_registered_model(name)
        except Exception:self.client.create_registered_model(name)
        version=self.client.create_model_version(name,source=f'runs:/{runid}/evaluation.json',run_id=runid)
        # Deliberately candidate, never automatically approved/validated.
        self.client.set_registered_model_alias(name,'candidate',version.version)
        return {'run_id':runid,'version':version.version}

class OpenBao(API):
    def __init__(self):super().__init__(required('BAO_URL'),{'X-Vault-Token':required('BAO_TOKEN')})
    def read(self,path):
        if not path or '..' in path:raise ValueError('invalid secret path')
        return self.call('GET','/v1/secret/data/'+quote(path,safe='/'))['data']['data']
    def write(self,path,value):return self.call('POST','/v1/secret/data/'+quote(path,safe='/'),{'data':value})

class IRIS(API):
    def __init__(self):super().__init__(required('IRIS_URL'),{'Authorization':'Bearer '+required('IRIS_TOKEN')})
    def alert(self,event_id,body):
        customer=int(required('IRIS_CUSTOMER_ID'))
        # Receiver-side lookup makes normal retries idempotent; a lost-response
        # concurrent race still requires a single delivery worker + reconciliation.
        found=self.call('GET','/alerts/filter',params={'alert_source_ref':event_id,'alert_customer_id':customer})
        data=found.get('data',{})
        if isinstance(data,dict) and data.get('alerts'):return data['alerts'][0]
        return self.call('POST','/alerts/add',{'alert_title':'Agent action denied','alert_description':json.dumps(body),
          'alert_source':'governed-agent-fabric','alert_source_ref':event_id,'alert_customer_id':customer,
          'alert_severity_id':3,'alert_status_id':2,'alert_tags':'agent-governance'})

class GLPI(API):
    def __init__(self):
        setting('GLPI_SERVICE_TYPE','Computer',api_identifier=True)
        super().__init__(required('GLPI_URL'),{'App-Token':required('GLPI_APP_TOKEN'),
                                             'Authorization':'user_token '+required('GLPI_USER_TOKEN')})
        session=self.call('GET','/initSession')['session_token']
        self.client.headers['Session-Token']=session
    def service(self,*,service_type=None,service_id=None,entity_id=None):
        kind=setting('GLPI_SERVICE_TYPE','Computer',override=service_type,api_identifier=True)
        service_id=setting('GLPI_SERVICE_ID',override=service_id)
        entity_id=setting('GLPI_ENTITY_ID',override=entity_id)
        record=self.call('GET','/'+kind+'/'+quote(service_id,safe=''))
        if str(record.get('entities_id'))!=entity_id:raise DependencyFailure('Service inventory entity mismatch')
        return record
    def remediation(self,title,description):
        return self.call('POST','/Ticket',{'input':{'name':title,'content':description,'type':2,
            'entities_id':int(required('GLPI_ENTITY_ID'))}})
    def close(self):
        try:self.call('GET','/killSession')
        finally:super().close()

class Ollama(API):
    def __init__(self):super().__init__(required('OLLAMA_URL'))
    def pull(self):
        # Cold model downloads are commissioning operations, not 10-second API calls.
        try:
            with httpx.Client(timeout=httpx.Timeout(900,connect=10),follow_redirects=False,trust_env=False) as c:
                r=c.post(self.base+'/api/pull',json={'model':required('OLLAMA_MODEL'),'stream':False})
                r.raise_for_status();return r.json()
        except (httpx.HTTPError,ValueError) as e:raise DependencyFailure('Ollama model pull failed') from e
    def propose(self,request):
        # Only a proposal. Identity, approval, source status and budget cannot be set.
        body={'model':required('OLLAMA_MODEL'),'prompt':request,'stream':False,'format':'json',
              'options':{'temperature':0,'num_predict':256}}
        with httpx.Client(timeout=180,follow_redirects=False,trust_env=False) as c:
            r=c.post(self.base+'/api/generate',json=body);r.raise_for_status();data=r.json()
        return {'proposal':json.loads(data['response']),'model':data.get('model'),
                'prompt_tokens':data.get('prompt_eval_count'),'output_tokens':data.get('eval_count')}
