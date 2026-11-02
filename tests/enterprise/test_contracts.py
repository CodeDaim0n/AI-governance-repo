"""Native adapter contracts using explicit simulated HTTP responses.
These tests are not counted as native product integration or all-18 acceptance.
"""
import json,os,time,unittest
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
import httpx
from fabric.enterprise.clients import API,OpenFGA,CISOAssistant,OpenMetadata,OpenBao,MLflowRegistry,DependencyFailure,Keycloak
from fabric.enterprise.policy import EnterprisePolicy
from fabric.enterprise.app import Action
from fabric.core import VERSION

class NativeContracts(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'FGA_URL':'http://fga.local','FGA_TOKEN':'synthetic-token','FGA_STORE_ID':'store',
   'FGA_MODEL_ID':'model','CISO_URL':'http://ciso.local/api','CISO_TOKEN':'synthetic-token','CISO_ASSESSMENT_ID':'assessment',
   'CISO_FOLDER_ID':'folder','METADATA_URL':'http://metadata.local/api','METADATA_TOKEN':'synthetic-token',
   'METADATA_TABLE_FQN':'fabric.credit.public.cases','METADATA_REQUIRED_TAG':'PII.Sensitive',
   'BAO_URL':'http://bao.local','BAO_TOKEN':'synthetic-token','MODEL_NAME':'fabric-credit-proposal','FAIRNESS_MAX_DIFFERENCE':'0.2','MODEL_TENANT':'bank-a'})
  self.env.start();self.apis=[]
 def tearDown(self):
  for api in self.apis:api.close()
  self.env.stop()
 def client(self,cls,handler):
  c=cls();c.client.close();c.client=httpx.Client(transport=httpx.MockTransport(handler),follow_redirects=False)
  self.apis.append(c);return c
 def model(self,metrics=None,tags=None):
  c=MLflowRegistry.__new__(MLflowRegistry);c.client=MagicMock()
  c.client.get_model_version_by_alias.return_value=SimpleNamespace(run_id='run',version='1')
  c.client.get_run.return_value=SimpleNamespace(data=SimpleNamespace(
   metrics={'fairness_difference':0.0} if metrics is None else metrics,
   tags={'fabric.validation_expires':str(time.time()+300),'fabric.independent_approval':'true'} if tags is None else tags))
  return c
 def test_absolute_action_endpoint_rejected(self):
  c=API('http://safe.local');self.apis.append(c)
  with self.assertRaises(ValueError):c.call('GET','https://other.local/secret')
 def test_redirect_not_followed(self):
  requests=[]
  c=API('http://safe.local');self.apis.append(c);c.client.close()
  c.client=httpx.Client(transport=httpx.MockTransport(lambda r:(requests.append(r) or httpx.Response(307,headers={'Location':'http://attacker.local'}))))
  with self.assertRaises(DependencyFailure):c.call('GET','/probe')
  self.assertEqual(len(requests),1)
 def test_product_error_body_not_exposed(self):
  c=self.client(OpenFGA,lambda r:httpx.Response(403,json={'secret':'do-not-leak'}))
  with self.assertRaises(DependencyFailure) as e:c.check('a','b')
  self.assertNotIn('do-not-leak',str(e.exception))
 def test_fga_string_true_does_not_grant_access(self):
  c=self.client(OpenFGA,lambda r:httpx.Response(200,json={'allowed':'true'}))
  with self.assertRaises(DependencyFailure):c.check('a','b')
 def test_fga_boolean_deny(self):
  c=self.client(OpenFGA,lambda r:httpx.Response(200,json={'allowed':False}));self.assertFalse(c.check('a','b'))
 def test_fga_model_and_consistency_bound(self):
  payload=[]
  def handler(r):payload.append(json.loads(r.content));return httpx.Response(200,json={'allowed':True})
  self.assertTrue(self.client(OpenFGA,handler).check('a','b'))
  self.assertEqual(payload[0]['authorization_model_id'],'model');self.assertEqual(payload[0]['consistency'],'HIGHER_CONSISTENCY')
 def test_existing_risk_never_overwritten(self):
  requests=[]
  def handler(r):
   requests.append(r.method);return httpx.Response(200,json={'results':[{'ref_id':'R01','risk_assessment':'assessment','residual_risk':4,'accepted':True}]})
  c=self.client(CISOAssistant,handler);r=c.create_risk({'risk_id':'R01'})
  self.assertTrue(r['accepted']);self.assertEqual(requests,['GET'])
 def test_new_risk_does_not_set_rating_or_acceptance(self):
  payload=[]
  def handler(r):
   if r.method=='GET':return httpx.Response(200,json={'results':[]})
   payload.append(json.loads(r.content));return httpx.Response(201,json={'id':'risk'})
  c=self.client(CISOAssistant,handler)
  c.create_risk({'risk_id':'R01','title':'Test','scenario':'Test','control':'Test','assurance_status':'Unverified'})
  for key in ['accepted','residual_risk','current_proba','current_impact','treatment']:self.assertNotIn(key,payload[0])
 def test_ciso_relations_merge_from_detail_not_lightweight_list(self):
  patches=[]
  def handler(r):
   path=r.url.path
   if r.method=='PATCH':patches.append((path,json.loads(r.content)));return httpx.Response(200,json={'id':'updated'})
   if path=='/api/risk-scenarios/':body={'results':[{'id':'r','ref_id':'R01','risk_assessment':'assessment'}]}
   elif path=='/api/risk-scenarios/r/':body={'id':'r','folder':'folder','risk_assessment':'assessment','applied_controls':['owner-control']}
   elif path=='/api/applied-controls/':body={'results':[{'id':'c','name':'Fabric assessment R01 control','folder':'folder'}]}
   elif path=='/api/applied-controls/c/':body={'id':'c','folder':'folder','evidences':['owner-evidence']}
   elif path=='/api/evidences/':body={'results':[{'id':'new-evidence','name':'Fabric event evt','folder':'folder'}]}
   else:raise AssertionError(path)
   return httpx.Response(200,json=body)
  c=self.client(CISOAssistant,handler);c.control_for_risk({'risk_id':'R01','control':'fixture'});c.evidence('evt',{'risk_ids':['R01']})
  self.assertEqual(patches,[('/api/risk-scenarios/r/',{'applied_controls':['owner-control','c']}),('/api/applied-controls/c/',{'evidences':['owner-evidence','new-evidence']})])
 def test_ciso_wrong_detail_scope_fails_without_patch(self):
  methods=[]
  def handler(r):methods.append(r.method);return httpx.Response(200,json={'id':'c','folder':'wrong-folder','evidences':[]})
  c=self.client(CISOAssistant,handler)
  with self.assertRaises(DependencyFailure):c.detail('applied-controls',{'id':'c'})
  self.assertEqual(methods,['GET'])
 def test_metadata_requires_owner(self):
  c=self.client(OpenMetadata,lambda r:httpx.Response(200,json={'id':'t','tags':[{'tagFQN':'PII.Sensitive'}]}))
  with self.assertRaises(DependencyFailure):c.assert_classified()
 def test_metadata_requires_classification(self):
  c=self.client(OpenMetadata,lambda r:httpx.Response(200,json={'id':'t','owners':[{'id':'u'}],'tags':[]}))
  with self.assertRaises(DependencyFailure):c.assert_classified()
 def test_metadata_records_version(self):
  c=self.client(OpenMetadata,lambda r:httpx.Response(200,json={'id':'t','version':2,'owners':[{'id':'u'}],'tags':[{'tagFQN':'PII.Sensitive'}]}))
  self.assertEqual(c.assert_classified()['version'],2)
 def test_secret_path_traversal_rejected(self):
  c=self.client(OpenBao,lambda r:(_ for _ in ()).throw(AssertionError('network must not be used')))
  with self.assertRaises(ValueError):c.read('../worker')
 def test_unapproved_model_is_denied(self):
  c=self.model(tags={'fabric.validation_expires':str(time.time()+300),'fabric.independent_approval':'false'})
  with self.assertRaises(DependencyFailure):c.validate()
 def test_expired_model_is_denied(self):
  c=self.model(tags={'fabric.validation_expires':'1','fabric.independent_approval':'true'})
  with self.assertRaises(DependencyFailure):c.validate()
 def test_missing_fairness_measure_is_denied(self):
  with self.assertRaises(DependencyFailure):self.model(metrics={}).validate()
 def test_exceeded_fairness_threshold_is_denied(self):
  with self.assertRaises(DependencyFailure):self.model(metrics={'fairness_difference':0.3}).validate()
 def test_validated_release_receipt(self):self.assertEqual(self.model().validate()['run_id'],'run')
 def test_agent_cannot_add_role_to_action(self):
  with self.assertRaises(Exception):Action(case_id='a',tool='credit.commit',amount_pence=1,idempotency_key='k',role='admin')
 def test_boolean_money_rejected_at_api(self):
  with self.assertRaises(Exception):Action(case_id='a',tool='credit.commit',amount_pence=True,idempotency_key='k')
 def test_local_deny_does_not_contact_remote_authorities(self):
  p=EnterprisePolicy('http://opa.local');p.opa=SimpleNamespace(decide=lambda x:{'allow':False,'reasons':['kill_switch'],'version':VERSION})
  with patch('fabric.enterprise.policy.OpenFGA',side_effect=AssertionError('Must not contact product')):
   self.assertFalse(p.decide({})['allow'])
 def test_relationship_deny_cannot_be_overridden(self):
  p=EnterprisePolicy('http://opa.local');p.opa=SimpleNamespace(decide=lambda x:{'allow':True,'reasons':[],'version':VERSION})
  f=MagicMock();f.check.return_value=False
  with patch('fabric.enterprise.policy.OpenFGA',return_value=f),patch('fabric.enterprise.policy.OpenMetadata'),patch('fabric.enterprise.policy.GLPI',side_effect=AssertionError('Must not reach inventory')):
   self.assertFalse(p.decide({'principal':{'id':'a','tenant':'bank-a'},'case':{'id':'b'}})['allow'])
   self.assertIn('model_tenant_not_validated',p.decide({'principal':{'id':'a','tenant':'bank-b'},'case':{'id':'b'}})['reasons'])

class TokenContracts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import jwt
  from cryptography.hazmat.primitives.asymmetric import rsa
  cls.jwt=jwt;cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
 def identity(self):
  c=Keycloak.__new__(Keycloak);c.jwt=self.jwt;c.issuer='https://issuer.local/realms/fabric'
  c.jwks=SimpleNamespace(get_signing_key_from_jwt=lambda t:SimpleNamespace(key=self.key.public_key()))
  return c
 def token(self,**overrides):
  c={'sub':'service-account','iss':'https://issuer.local/realms/fabric','aud':'fabric-gateway','iat':int(time.time()),'exp':int(time.time())+60,'fabric_principal':'agent-a',**overrides}
  return self.jwt.encode(c,self.key,algorithm='RS256')
 def test_signed_mapped_identity(self):self.assertEqual(self.identity().verify(self.token()),'agent-a')
 def test_wrong_gateway_audience(self):
  with self.assertRaises(DependencyFailure):self.identity().verify(self.token(aud='other'))
 def test_unmapped_identity(self):
  with self.assertRaises(DependencyFailure):self.identity().verify(self.token(fabric_principal='superuser'))
 def test_expired_native_profile(self):
  with self.assertRaises(DependencyFailure):self.identity().verify(self.token(exp=1))
 def test_wrong_issuer(self):
  with self.assertRaises(DependencyFailure):self.identity().verify(self.token(iss='https://other.local'))
if __name__=='__main__':unittest.main()
