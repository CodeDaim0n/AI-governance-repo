import concurrent.futures
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fabric.core import Fabric, OPA, Rejected, VERSION
from fabric.auth import issue, verify
from fabric.server import make_handler
from fabric.outbox import deliver

class FabricTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.now=1000
  self.f=Fabric(Path(self.tmp.name)/'lab.db',clock=lambda:self.now);self.f.seed()
 def tearDown(self): self.tmp.cleanup()
 def action(self,amount=50000,key='a',**kw): return {'case_id':'case-a','tool':'credit.commit','amount_pence':amount,'idempotency_key':key,**kw}
 def deny(self,a,reason,actor='agent-a',approval=None):
  r=self.f.execute(actor,a,approval);self.assertEqual(r['status'],'denied');self.assertIn(reason,r['reason'])
 def update(self,sql,*args):
  with self.f.tx() as c:c.execute(sql,args)
 def test_low_value_executes(self): self.assertEqual(self.f.execute('agent-a',self.action())['status'],'executed')
 def test_cross_tenant(self): self.deny(self.action(case_id='case-b'),'tenant_boundary')
 def test_unlisted_tool(self): self.deny(self.action(tool='shell.exec'),'tool_not_allowed')
 def test_prompt_cannot_grant_identity(self):
  with self.assertRaises(Rejected):self.f.execute('agent-a',{**self.action(),'role':'admin'})
 def test_kyc_fail(self):
  self.update("UPDATE cases SET kyc='blocked' WHERE id='case-a'");self.deny(self.action(),'kyc_not_clear')
 def test_region(self):
  self.update("UPDATE cases SET region='US' WHERE id='case-a'");self.deny(self.action(),'region_not_allowed')
 def test_stale_source(self):self.now+=61;self.deny(self.action(),'stale_context')
 def test_future_source(self):
  self.update('UPDATE cases SET updated=2000');self.deny(self.action(),'future_context')
 def test_missing_case(self):self.deny(self.action(case_id='missing'),'case_unknown')
 def test_workflow_revoked(self):
  self.update('UPDATE registry SET approved=0');self.deny(self.action(),'workflow_not_approved')
 def test_validation_expired(self):
  self.update('UPDATE registry SET validated_until=999');self.deny(self.action(),'validation_expired')
 def test_human_gate(self):self.deny(self.action(200000),'human_approval_required')
 def test_approval_executes(self):
  a=self.action(200000);i=self.f.approve('reviewer-a','agent-a',a)
  self.assertEqual(self.f.execute('agent-a',a,i)['status'],'executed')
 def test_approval_amount_substitution(self):
  i=self.f.approve('reviewer-a','agent-a',self.action(200000));self.deny(self.action(300000),'human_approval_required',approval=i)
 def test_approval_case_version_change(self):
  a=self.action(200000);i=self.f.approve('reviewer-a','agent-a',a)
  self.update("UPDATE cases SET version=version+1 WHERE id='case-a'");self.deny(a,'human_approval_required',approval=i)
 def test_approval_workflow_version_change(self):
  a=self.action(200000);i=self.f.approve('reviewer-a','agent-a',a)
  self.update("UPDATE registry SET version='workflow-2'");self.deny(a,'human_approval_required',approval=i)
 def test_expired_approval(self):
  a=self.action(200000);i=self.f.approve('reviewer-a','agent-a',a)
  self.now+=301;self.update('UPDATE cases SET updated=?',self.now);self.deny(a,'human_approval_required',approval=i)
 def test_reviewer_revocation(self):
  a=self.action(200000);i=self.f.approve('reviewer-a','agent-a',a)
  self.update("UPDATE principals SET active=0 WHERE id='reviewer-a'");self.deny(a,'identity_inactive',approval=i)
 def test_wrong_reviewer_tenant(self):
  with self.assertRaises(Rejected): self.f.approve('reviewer-b','agent-a',self.action(200000))
 def test_self_approval(self):
  with self.assertRaises(Rejected):self.f.approve('agent-a','agent-a',self.action(200000))
 def test_hard_limit_not_overridable(self):
  with self.assertRaises(Rejected):self.f.approve('reviewer-a','agent-a',self.action(1000001))
 def test_kill_switch(self):self.f.stop('admin-a');self.deny(self.action(),'kill_switch')
 def test_kill_authority(self):
  with self.assertRaises(Rejected):self.f.stop('agent-a')
 def test_idempotent_retry(self):
  a=self.action();self.assertEqual(self.f.execute('agent-a',a),self.f.execute('agent-a',a))
  with self.f.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM actions').fetchone()[0],1)
 def test_idempotency_conflict(self):
  self.f.execute('agent-a',self.action())
  with self.assertRaises(Rejected):self.f.execute('agent-a',self.action(60000))
 def test_cumulative_budget(self):
  for key in ['a','b']:
   a=self.action(700000,key);i=self.f.approve('reviewer-a','agent-a',a);self.f.execute('agent-a',a,i)
  self.deny(self.action(100001,'c'),'aggregate_budget')
 def test_concurrent_budget(self):
  actions=[self.action(100000,str(i)) for i in range(20)]
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:r=list(pool.map(lambda a:self.f.execute('agent-a',a),actions))
  self.assertEqual(sum(x['status']=='executed' for x in r),15)
 def test_policy_outage(self):
  self.f.policy=OPA('http://127.0.0.1:1/no');self.deny(self.action(),'policy_unavailable')
 def test_bad_policy_response(self):
  class Bad:
   def decide(s,x):raise ValueError('malformed')
  self.f.policy=Bad();self.deny(self.action(),'policy_unavailable')
 def test_audit_atomicity(self):
  with self.f.tx() as c:c.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT,'disk'); END")
  with self.assertRaises(Exception):self.f.execute('agent-a',self.action())
  with self.f.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM actions').fetchone()[0],0)
 def test_audit_tamper(self):
  self.f.execute('agent-a',self.action());self.assertTrue(self.f.verify_chain())
  self.update("UPDATE audit SET body='corrupt'");self.assertFalse(self.f.verify_chain())
 def test_no_raw_action_in_evidence(self):
  self.f.execute('agent-a',self.action())
  with self.f.connect() as c:
   body=c.execute('SELECT body FROM audit').fetchone()[0];self.assertNotIn('case-a',body);self.assertNotIn('amount_pence',body)
 def test_restart_persistence(self):
  a=self.action();r=self.f.execute('agent-a',a);other=Fabric(self.f.path,clock=lambda:self.now)
  self.assertEqual(other.execute('agent-a',a),r)
 def test_integer_money(self):
  for n in [True,-1,0,1.1,float('nan')]:
   with self.assertRaises(Rejected):self.f.execute('agent-a',self.action(n))
 def test_outbox_delivery(self):
  received=[]
  class Sink(BaseHTTPRequestHandler):
   def log_message(self,*a):pass
   def do_POST(s):
    received.append(s.headers['Idempotency-Key']);s.rfile.read(int(s.headers['Content-Length']));s.send_response(204);s.end_headers()
  srv=ThreadingHTTPServer(('127.0.0.1',0),Sink);thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
  try:
   self.f.execute('agent-a',self.action());self.assertEqual(deliver(self.f.path,f'http://127.0.0.1:{srv.server_port}/'),1)
   self.assertEqual(deliver(self.f.path,f'http://127.0.0.1:{srv.server_port}/'),0);self.assertEqual(len(received),1)
  finally:srv.shutdown();srv.server_close()
 def test_outbox_outage_preserves_event(self):
  self.f.execute('agent-a',self.action())
  with self.assertRaises(Exception):deliver(self.f.path,'http://127.0.0.1:1/no')
  with self.f.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM outbox WHERE delivered=0').fetchone()[0],1)

class AuthTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  cls.priv=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
  cls.pub=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
 def test_signed_identity(self):self.assertEqual(verify(self.pub,issue(self.priv,'agent-a')),'agent-a')
 def test_wrong_audience(self):
  with self.assertRaises(Rejected):verify(self.pub,issue(self.priv,'agent-a',aud='other'))
 def test_expired(self):
  with self.assertRaises(Rejected):verify(self.pub,issue(self.priv,'agent-a',lifetime=-1))
 def test_forged_signature(self):
  t=issue(self.priv,'agent-a');h,p,s=t.split('.')
  with self.assertRaises(Rejected):verify(self.pub,h+'.'+p+'.'+('A' if s[0]!='A' else 'B')+s[1:])
 def test_unsigned(self):
  with self.assertRaises(Rejected):verify(self.pub,'eyJhbGciOiJub25lIn0.e30.')
 def test_http_signed_and_unsigned(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Fabric(Path(tmp)/'http.db');f.seed();srv=ThreadingHTTPServer(('127.0.0.1',0),make_handler(f,self.pub));threading.Thread(target=srv.serve_forever,daemon=True).start()
   url=f'http://127.0.0.1:{srv.server_port}/execute';body=json.dumps({'action':{'case_id':'case-a','tool':'credit.commit','amount_pence':1000,'idempotency_key':'http'}}).encode()
   try:
    with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(urllib.request.Request(url,body,{'X-Actor':'admin-a'}))
    req=urllib.request.Request(url,body,{'Authorization':'Bearer '+issue(self.priv,'agent-a')})
    with urllib.request.urlopen(req) as r:self.assertEqual(json.load(r)['status'],'executed')
   finally:srv.shutdown();srv.server_close()

if __name__=='__main__':unittest.main()
