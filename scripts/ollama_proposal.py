"""Optional model proposal only. Not used to generate security test results."""
import json
import os
import urllib.request
prompt='Propose a synthetic credit.commit action for case-a for 50000 pence. Return only JSON with case_id, tool, amount_pence, idempotency_key. No other fields.'
request=urllib.request.Request('http://127.0.0.1:11434/api/generate',json.dumps({'model':os.getenv('MODEL','qwen2.5:0.5b'),'prompt':prompt,'stream':False,'format':'json','options':{'temperature':0}}).encode(),{'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=120) as r: print(json.loads(json.load(r)['response']))
