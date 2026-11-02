"""Single-node enforcement laboratory. No public deployment surface."""
import contextlib
import hashlib
import json
import sqlite3
import time
import urllib.request
import uuid

VERSION = 'credit-policy-1'
def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

class Rejected(Exception):
    pass

class OPA:
    def __init__(self, url='http://127.0.0.1:8181/v1/data/fabric/decision'):
        self.url = url
    def decide(self, value):
        request = urllib.request.Request(self.url, canonical({'input': value}).encode(), {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=2) as response:
            result = json.load(response)['result']
        if type(result.get('allow')) is not bool or result.get('version') != VERSION:
            raise ValueError('invalid or unexpected policy response')
        return result

class Fabric:
    """All policy context is server-owned. SQLite serializes budget/action/audit writes.
    The Python principal argument is a trusted boundary; HTTP derives it from JWT.
    """
    def __init__(self, path, policy=None, clock=time.time):
        self.path, self.policy, self.clock = str(path), policy or OPA(), clock
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS principals(id TEXT PRIMARY KEY,tenant TEXT,role TEXT,active INT);
            CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,tenant TEXT,kyc TEXT,region TEXT,version INT,updated REAL);
            CREATE TABLE IF NOT EXISTS registry(id TEXT PRIMARY KEY,approved INT,version TEXT,validated_until REAL);
            CREATE TABLE IF NOT EXISTS switches(id TEXT PRIMARY KEY,stopped INT);
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,actor TEXT,approver TEXT,hash TEXT,expires REAL,used INT);
            CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY,actor TEXT,tenant TEXT,idem TEXT,hash TEXT,amount INT,response TEXT,UNIQUE(actor,tenant,idem));
            CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY,body TEXT,previous TEXT,hash TEXT);
            CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,kind TEXT,body TEXT,delivered INT DEFAULT 0);
            ''')
    def connect(self):
        c = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        c.row_factory = sqlite3.Row
        return c
    @contextlib.contextmanager
    def tx(self):
        c = self.connect()
        try:
            c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()
    def seed(self):
        now = self.clock()
        with self.tx() as c:
            c.executemany('INSERT OR REPLACE INTO principals VALUES(?,?,?,1)', [
                ('agent-a','bank-a','agent'),('reviewer-a','bank-a','reviewer'),
                ('reviewer-b','bank-b','reviewer'),('admin-a','bank-a','admin'),('agent-b','bank-b','agent')])
            c.executemany('INSERT OR REPLACE INTO cases VALUES(?,?,?,?,1,?)', [
                ('case-a','bank-a','clear','UK',now),('case-b','bank-b','clear','UK',now)])
            c.execute('INSERT OR REPLACE INTO registry VALUES(?,?,?,?)', ('credit-workflow',1,'workflow-1',now+86400))
            c.execute('INSERT OR IGNORE INTO switches VALUES(?,0)', ('credit-workflow',))
    def principal(self,c,actor):
        p = c.execute('SELECT * FROM principals WHERE id=?',(actor,)).fetchone()
        if not p or not p['active']: raise Rejected('identity_inactive')
        return dict(p)
    def validate(self,action):
        if type(action) is not dict or set(action) != {'case_id','tool','amount_pence','idempotency_key'}:
            raise Rejected('invalid_schema')
        for key in ['case_id','tool','idempotency_key']:
            if type(action[key]) is not str or not 1 <= len(action[key]) <= 128: raise Rejected('invalid_schema')
        if type(action['amount_pence']) is not int or not 0 < action['amount_pence'] <= 10**9:
            raise Rejected('invalid_amount')
    def context(self,c,actor,action):
        p = self.principal(c,actor)
        case = c.execute('SELECT * FROM cases WHERE id=?',(action['case_id'],)).fetchone()
        if not case: raise Rejected('case_unknown')
        registry = dict(c.execute('SELECT * FROM registry WHERE id=?',('credit-workflow',)).fetchone())
        stopped = c.execute('SELECT stopped FROM switches WHERE id=?',('credit-workflow',)).fetchone()[0]
        spent = c.execute('SELECT COALESCE(SUM(amount),0) FROM actions WHERE tenant=?',(p['tenant'],)).fetchone()[0]
        return {'principal':p,'case':dict(case),'registry':registry,'stopped':bool(stopped),
                'spent':spent,'now':self.clock(),'action':action,'approved':False}
    def bound_hash(self,ctx):
        return digest({'action':ctx['action'],'actor':ctx['principal']['id'],
            'case_version':ctx['case']['version'],'workflow_version':ctx['registry']['version'],'policy_version':VERSION})
    def event(self,c,event):
        previous = c.execute('SELECT hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
        previous = previous[0] if previous else '0'*64
        body = canonical({'time':self.clock(),**event})
        h = hashlib.sha256((previous+body).encode()).hexdigest()
        c.execute('INSERT INTO audit(body,previous,hash) VALUES(?,?,?)',(body,previous,h))
        eid = str(uuid.uuid4())
        c.execute('INSERT INTO outbox(id,kind,body) VALUES(?,?,?)',(eid,'evidence',body))
        if event.get('outcome') == 'denied':
            c.execute('INSERT INTO outbox(id,kind,body) VALUES(?,?,?)',(str(uuid.uuid4()),'incident',canonical({'event_id':eid,'reason':event['reason']})))
    def approve(self,reviewer,actor,action):
        self.validate(action)
        with self.tx() as c:
            r = self.principal(c,reviewer)
            ctx = self.context(c,actor,action)
            if reviewer == actor or r['role'] != 'reviewer' or r['tenant'] != ctx['case']['tenant'] or r['tenant'] != ctx['principal']['tenant']:
                raise Rejected('approval_authority')
            # Approval cannot override a hard policy denial.
            ctx['approved'] = True
            try: d = self.policy.decide(ctx)
            except Exception as e: raise Rejected('policy_unavailable') from e
            if not d['allow']: raise Rejected('approval_ineligible')
            aid = str(uuid.uuid4())
            c.execute('INSERT INTO approvals VALUES(?,?,?,?,?,0)',(aid,actor,reviewer,self.bound_hash(ctx),self.clock()+300))
            self.event(c,{'actor':reviewer,'outcome':'approved','action_hash':self.bound_hash(ctx),'approval_id':aid,'policy':VERSION})
            return aid
    def execute(self,actor,action,approval_id=None):
        self.validate(action)
        result = None
        with self.tx() as c:
            # Authentication precedes use of tenant-scoped state.
            p = self.principal(c,actor)
            old = c.execute('SELECT * FROM actions WHERE actor=? AND tenant=? AND idem=?',(actor,p['tenant'],action['idempotency_key'])).fetchone()
            if old:
                if old['hash'] != digest(action): raise Rejected('idempotency_conflict')
                return json.loads(old['response'])
            try:
                ctx = self.context(c,actor,action)
                aid = c.execute('SELECT * FROM approvals WHERE id=?',(approval_id,)).fetchone()
                if aid:
                    reviewer = self.principal(c,aid['approver'])
                    ctx['approved'] = bool(not aid['used'] and aid['expires'] > self.clock() and
                        aid['actor'] == actor and aid['hash'] == self.bound_hash(ctx) and reviewer['role'] == 'reviewer' and
                        reviewer['tenant'] == p['tenant'] and reviewer['id'] != actor)
                try: d = self.policy.decide(ctx)
                except Exception as e: raise Rejected('policy_unavailable') from e
                if not d['allow']: raise Rejected(','.join(d.get('reasons',[])) or 'policy_denied')
                response = {'status':'executed','action_id':str(uuid.uuid4()),'policy':VERSION}
                # Synthetic credit ledger is the target. Never call a real bank.
                c.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?)',(response['action_id'],actor,p['tenant'],action['idempotency_key'],digest(action),action['amount_pence'],canonical(response)))
                if ctx['approved']: c.execute('UPDATE approvals SET used=1 WHERE id=?',(approval_id,))
                self.event(c,{'actor':actor,'outcome':'executed','action_hash':digest(action),'action_id':response['action_id'],'case_version':ctx['case']['version'],'policy':VERSION})
                result = response
            except Rejected as e:
                self.event(c,{'actor':actor,'outcome':'denied','action_hash':digest(action),'reason':str(e),'policy':VERSION})
                result = {'status':'denied','reason':str(e)}
        return result
    def stop(self,actor,stopped=True):
        with self.tx() as c:
            p = self.principal(c,actor)
            if p['role'] != 'admin': raise Rejected('admin_required')
            c.execute('UPDATE switches SET stopped=? WHERE id=?',(int(stopped),'credit-workflow'))
            self.event(c,{'actor':actor,'outcome':'stopped' if stopped else 'resumed','policy':VERSION})
    def verify_chain(self):
        previous = '0'*64
        with self.connect() as c:
            for r in c.execute('SELECT * FROM audit ORDER BY seq'):
                if r['previous'] != previous or r['hash'] != hashlib.sha256((previous+r['body']).encode()).hexdigest(): return False
                previous = r['hash']
        return True
