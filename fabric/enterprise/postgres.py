"""PostgreSQL implementation of the core storage interface.
A single shared guard row serializes commit-time authority and budget checks.
"""
import re
from fabric.core import Fabric
class Row(dict):
 def __getitem__(self,key):return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)
class Cursor:
 def __init__(self,c):self.c=c
 def fetchone(self):
  r=self.c.fetchone();return Row(r) if r is not None else None
 def fetchall(self):return [Row(r) for r in self.c.fetchall()]
 def __iter__(self):return iter(self.fetchall())
class Connection:
 def __init__(self,dsn):
  import psycopg
  from psycopg.rows import dict_row
  self.c=psycopg.connect(dsn,autocommit=True,row_factory=dict_row)
 def execute(self,sql,args=()):
  if sql=='BEGIN IMMEDIATE':
   self.c.execute('BEGIN');self.c.execute('SELECT id FROM fabric_guard WHERE id=1 FOR UPDATE');return Cursor(self.c.cursor())
  return Cursor(self.c.execute(sql.replace('?', '%s'),args))
 def executescript(self,sql):
  self.c.execute('CREATE TABLE IF NOT EXISTS fabric_guard(id INTEGER PRIMARY KEY)')
  self.c.execute('INSERT INTO fabric_guard VALUES(1) ON CONFLICT DO NOTHING')
  sql=sql.replace('seq INTEGER PRIMARY KEY','seq BIGSERIAL PRIMARY KEY').replace(' REAL',' DOUBLE PRECISION')
  for statement in sql.split(';'):
   if statement.strip():self.c.execute(statement)
 def commit(self):self.c.execute('COMMIT')
 def rollback(self):self.c.execute('ROLLBACK')
 def close(self):self.c.close()
 def __enter__(self):return self
 def __exit__(self,*a):self.close()
class PostgresFabric(Fabric):
 def connect(self):return Connection(self.path)
 def seed(self):
  now=self.clock()
  with self.tx() as c:
   for actor,tenant,role in [('agent-a','bank-a','agent'),('reviewer-a','bank-a','reviewer'),('reviewer-b','bank-b','reviewer'),('admin-a','bank-a','admin'),('agent-b','bank-b','agent')]:
    c.execute('INSERT INTO principals VALUES(?,?,?,1) ON CONFLICT(id) DO NOTHING',(actor,tenant,role))
   for case,tenant in [('case-a','bank-a'),('case-b','bank-b')]:
    c.execute('INSERT INTO cases VALUES(?,?,?, ?,1,?) ON CONFLICT(id) DO NOTHING',(case,tenant,'clear','UK',now))
   c.execute('INSERT INTO registry VALUES(?,?,?,?) ON CONFLICT(id) DO NOTHING',('credit-workflow',0,'workflow-1',0))
   c.execute('INSERT INTO switches VALUES(?,0) ON CONFLICT(id) DO NOTHING',('credit-workflow',))
