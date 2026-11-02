"""At-least-once HTTP delivery; receiver must deduplicate Idempotency-Key.
Use trusted configured endpoint only; never accept endpoints from model output.
"""
import urllib.request
from .core import Fabric

def deliver(db, endpoint):
    f=Fabric(db); count=0
    with f.connect() as c: rows=c.execute('SELECT * FROM outbox WHERE delivered=0 ORDER BY rowid LIMIT 100').fetchall()
    for row in rows:
        request=urllib.request.Request(endpoint,row['body'].encode(),{'Content-Type':'application/json','Idempotency-Key':row['id'],'X-Event-Kind':row['kind']})
        with urllib.request.urlopen(request,timeout=2) as response:
            if not 200<=response.status<300: raise RuntimeError('delivery_failed')
        with f.tx() as c: c.execute('UPDATE outbox SET delivered=1 WHERE id=?',(row['id'],))
        count+=1
    return count
