"""Native GRC, incident and remediation delivery with per-sink durable receipts.
Do not run concurrent dispatchers. Lost remote responses require reconciliation.
"""
import json,time,os,hashlib
from contextlib import contextmanager
from .clients import OpenBao,CISOAssistant,IRIS,GLPI,required
from .postgres import PostgresFabric,Connection
from .configuration import (DEFAULT_RISK_REASON,ConfigurationError,dispatch_risk_mapping,
                            executed_risk_ids,dispatch_storage_mode,workflow_risk_bindings,text_value)
RISK_REASON=DEFAULT_RISK_REASON  # Backward-compatible name; execution reads configuration.
TABLES={
 'legacy':{'outbox':'outbox','principals':'principals','receipts':'sink_receipts','correlations':'incident_correlations'},
 'configurable':{'outbox':'cfg_outbox','principals':'cfg_principals','receipts':'cfg_sink_receipts','correlations':'cfg_incident_correlations'},
}
PLATFORM_EVIDENCE_OUTCOMES={'principal_provisioned','principal_revoked','model_approved','stopped','resumed'}


class DispatchStore:
 """Dispatch-only connection: generic mode does not create legacy domain tables."""
 def __init__(self,dsn):self.dsn=dsn
 def connect(self):return Connection(self.dsn)
 @contextmanager
 def tx(self):
  with self.connect() as c:
   c.execute('BEGIN')
   try:
    yield c
    c.commit()
   except Exception:
    c.rollback();raise


def risk_ids(reasons,outcome,*,mapping=None,executed=None):
 mapping=dispatch_risk_mapping() if mapping is None else mapping
 executed=executed_risk_ids() if executed is None else executed
 return sorted(set(executed if outcome=='executed' else [mapping[x] for x in reasons if x in mapping]))

def once():
 # Validate mappings before reading or delivering any outbox events.
 mode=dispatch_storage_mode();tables=TABLES[mode]
 if mode=='legacy':mapping=dispatch_risk_mapping();executed=executed_risk_ids()
 else:bindings=workflow_risk_bindings()
 from .telemetry import OUTBOX
 f=(PostgresFabric if mode=='legacy' else DispatchStore)(required('DATABASE_URL'))
 with f.tx() as c:
  c.execute(f"CREATE TABLE IF NOT EXISTS {tables['correlations']}(id TEXT,sink TEXT,receipt TEXT,PRIMARY KEY(id,sink))")
  c.execute(f"CREATE TABLE IF NOT EXISTS {tables['receipts']}(event_id TEXT,sink TEXT,receipt TEXT,PRIMARY KEY(event_id,sink))")
  rows=c.execute(f"SELECT * FROM {tables['outbox']} WHERE delivered=0 ORDER BY id LIMIT 50").fetchall()
 for row in rows:
  payload=json.loads(row['body']);sinks=['ciso']
  original=payload
  if row['kind']=='incident':
   with f.connect() as c:source=c.execute(f"SELECT body FROM {tables['outbox']} WHERE id=?",(payload.get('event_id'),)).fetchone()
   if source:original=json.loads(source['body'])
  reasons=payload.get('reason',original.get('reason','')).split(',')
  workflow_id=original.get('workflow_id')
  if mode=='configurable':
   if payload.get('workflow_id') is not None and payload['workflow_id']!=workflow_id:
    raise ConfigurationError('Incident workflow differs from its source evidence')
   if workflow_id is None:
    # Only explicit platform control/provisioning evidence may lack a workflow.
    # It has no process risk links and can never become an incident or ticket.
    if row['kind']!='evidence' or original.get('outcome') not in PLATFORM_EVIDENCE_OUTCOMES:
     raise ConfigurationError('Configurable workflow event requires workflow_id')
    payload['risk_ids']=[]
   else:
    text_value(workflow_id,'Dispatch workflow ID')
    if workflow_id not in bindings:raise ConfigurationError('Missing risk binding for workflow: '+workflow_id)
    binding=bindings[workflow_id]
    payload['risk_ids']=risk_ids(reasons,original.get('outcome'),mapping=binding['reason_to_risk'],executed=binding['executed_risk_ids'])
  else:payload['risk_ids']=risk_ids(reasons,original.get('outcome'),mapping=mapping,executed=executed)
  # Waiting for required approval is normal workflow behavior, not by itself
  # an attack. It still produces evidence but does not open an incident/ticket.
  approval_wait=set(reasons) in ({'human_approval_required'},{'approval_required'})
  if row['kind']=='incident' and not approval_wait:sinks+=['iris','glpi']
  with f.connect() as c:principal=c.execute(f"SELECT tenant FROM {tables['principals']} WHERE id=?",(original.get('actor'),)).fetchone()
  tenant=principal['tenant'] if principal else 'platform'
  bucket=str(int(float(original.get('time',time.time()))//3600))
  correlation_input=(tenant+'|'+','.join(sorted(reasons))+'|'+bucket if mode=='legacy' else
                     'configurable|'+json.dumps([workflow_id,tenant,sorted(reasons),bucket],separators=(',',':')))
  correlation=hashlib.sha256(correlation_input.encode()).hexdigest()

  for sink in sinks:
   with f.connect() as c:done=c.execute(f"SELECT receipt FROM {tables['receipts']} WHERE event_id=? AND sink=?",(row['id'],sink)).fetchone()
   if done:continue
   if sink!='ciso':
    with f.connect() as c:prior=c.execute(f"SELECT receipt FROM {tables['correlations']} WHERE id=? AND sink=?",(correlation,sink)).fetchone()
    if prior:
     with f.tx() as c:c.execute(f"INSERT INTO {tables['receipts']} VALUES(?,?,?) ON CONFLICT DO NOTHING",(row['id'],sink,prior['receipt']))
     continue
   client=CISOAssistant() if sink=='ciso' else IRIS() if sink=='iris' else GLPI()
   try:
    if sink=='ciso':receipt=client.evidence(row['id'],payload)
    elif sink=='iris':receipt=client.alert(correlation,payload)
    else:receipt=client.remediation('Fabric governance investigation '+correlation,json.dumps(payload))
   finally:client.close()
   with f.tx() as c:
    c.execute(f"INSERT INTO {tables['receipts']} VALUES(?,?,?) ON CONFLICT DO NOTHING",(row['id'],sink,json.dumps(receipt)))
    if sink!='ciso':c.execute(f"INSERT INTO {tables['correlations']} VALUES(?,?,?) ON CONFLICT DO NOTHING",(correlation,sink,json.dumps(receipt)))
  with f.tx() as c:c.execute(f"UPDATE {tables['outbox']} SET delivered=1 WHERE id=?",(row['id'],))
 with f.connect() as c:n=c.execute(f"SELECT count(*) FROM {tables['outbox']} WHERE delivered=0").fetchone()[0]
 OUTBOX.set(n);return len(rows)

def main():
 secret=OpenBao().read('fabric/dispatch')
 for k in ['CISO_TOKEN','IRIS_TOKEN','GLPI_APP_TOKEN','GLPI_USER_TOKEN']:os.environ[k]=secret[k]
 while True:
  try:once()
  except Exception:print('Native outbox delivery failed; event retained',flush=True)
  time.sleep(5)
if __name__=='__main__':main()
