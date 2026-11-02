"""Native GRC, incident and remediation delivery with per-sink durable receipts.
Do not run concurrent dispatchers. Lost remote responses require reconciliation.
"""
import json,time,os,hashlib
from .clients import OpenBao,CISOAssistant,IRIS,GLPI,required
from .postgres import PostgresFabric
from .telemetry import OUTBOX
RISK_REASON={'tenant_boundary':'R01','human_approval_required':'R02','stale_context':'R03','kyc_not_clear':'R03','aggregate_budget':'R04','policy_unavailable':'R09'}

def once():
 f=PostgresFabric(required('DATABASE_URL'))
 with f.tx() as c:
  c.execute('CREATE TABLE IF NOT EXISTS incident_correlations(id TEXT,sink TEXT,receipt TEXT,PRIMARY KEY(id,sink))')
  c.execute('CREATE TABLE IF NOT EXISTS sink_receipts(event_id TEXT,sink TEXT,receipt TEXT,PRIMARY KEY(event_id,sink))')
  rows=c.execute('SELECT * FROM outbox WHERE delivered=0 ORDER BY id LIMIT 50').fetchall()
 for row in rows:
  payload=json.loads(row['body']);sinks=['ciso']
  original=payload
  if row['kind']=='incident':
   with f.connect() as c:source=c.execute('SELECT body FROM outbox WHERE id=?',(payload.get('event_id'),)).fetchone()
   if source:original=json.loads(source['body'])
  reasons=payload.get('reason',original.get('reason','')).split(',')
  payload['risk_ids']=sorted({RISK_REASON[x] for x in reasons if x in RISK_REASON})
  if original.get('outcome')=='executed':payload['risk_ids']=['R01','R02','R04']
  # Waiting for required approval is normal workflow behavior, not by itself
  # an attack. It still produces evidence but does not open an incident/ticket.
  if row['kind']=='incident' and set(reasons)!={'human_approval_required'}:sinks+=['iris','glpi']
  with f.connect() as c:principal=c.execute('SELECT tenant FROM principals WHERE id=?',(original.get('actor'),)).fetchone()
  tenant=principal['tenant'] if principal else 'platform'
  bucket=str(int(float(original.get('time',time.time()))//3600))
  correlation=hashlib.sha256((tenant+'|'+','.join(sorted(reasons))+'|'+bucket).encode()).hexdigest()

  for sink in sinks:
   with f.connect() as c:done=c.execute('SELECT receipt FROM sink_receipts WHERE event_id=? AND sink=?',(row['id'],sink)).fetchone()
   if done:continue
   if sink!='ciso':
    with f.connect() as c:prior=c.execute('SELECT receipt FROM incident_correlations WHERE id=? AND sink=?',(correlation,sink)).fetchone()
    if prior:
     with f.tx() as c:c.execute('INSERT INTO sink_receipts VALUES(?,?,?) ON CONFLICT DO NOTHING',(row['id'],sink,prior['receipt']))
     continue
   client=CISOAssistant() if sink=='ciso' else IRIS() if sink=='iris' else GLPI()
   try:
    if sink=='ciso':receipt=client.evidence(row['id'],payload)
    elif sink=='iris':receipt=client.alert(correlation,payload)
    else:receipt=client.remediation('Fabric governance investigation '+correlation,json.dumps(payload))
   finally:client.close()
   with f.tx() as c:
    c.execute('INSERT INTO sink_receipts VALUES(?,?,?) ON CONFLICT DO NOTHING',(row['id'],sink,json.dumps(receipt)))
    if sink!='ciso':c.execute('INSERT INTO incident_correlations VALUES(?,?,?) ON CONFLICT DO NOTHING',(correlation,sink,json.dumps(receipt)))
  with f.tx() as c:c.execute('UPDATE outbox SET delivered=1 WHERE id=?',(row['id'],))
 with f.connect() as c:n=c.execute('SELECT count(*) FROM outbox WHERE delivered=0').fetchone()[0]
 OUTBOX.set(n);return len(rows)

def main():
 secret=OpenBao().read('fabric/dispatch')
 for k in ['CISO_TOKEN','IRIS_TOKEN','GLPI_APP_TOKEN','GLPI_USER_TOKEN']:os.environ[k]=secret[k]
 while True:
  try:once()
  except Exception:print('Native outbox delivery failed; event retained',flush=True)
  time.sleep(5)
if __name__=='__main__':main()
