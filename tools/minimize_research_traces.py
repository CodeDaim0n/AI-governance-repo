"""Publish minimized native SDK spans as valid JSONL; retain transformation hashes.
Raw model requests/responses are never changed. Private SDK source files remain
under .local; environment resource labels are unnecessary in a public study.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
allowed={'service.name','telemetry.sdk.name','telemetry.sdk.language','telemetry.sdk.version'}
receipts=[]
for path in sorted((ROOT/'results/native-agent').glob('*/traces.jsonl')):
 raw=path.read_bytes();text=raw.decode();offset=0;decoder=json.JSONDecoder();spans=[];removed=set()
 while offset<len(text):
  while offset<len(text) and text[offset].isspace():offset+=1
  if offset==len(text):break
  span,end=decoder.raw_decode(text,offset);offset=end
  attrs=span.get('resource',{}).get('attributes',{})
  removed.update(set(attrs)-allowed)
  span['resource']['attributes']={k:v for k,v in attrs.items() if k in allowed}
  spans.append(span)
 public=''.join(json.dumps(s,separators=(',',':'))+'\n' for s in spans).encode()
 path.write_bytes(public)
 receipts.append({'artifact':str(path.relative_to(ROOT)),'input_sha256':hashlib.sha256(raw).hexdigest(),'published_sha256':hashlib.sha256(public).hexdigest(),'spans':len(spans),'removed_resource_keys':sorted(removed),'transformation':'Resource attribute allowlist and canonical JSONL; span IDs, timestamps, outcomes and operations retained.'})
(ROOT/'results/native-agent/trace-minimization.json').write_text(json.dumps(receipts,indent=2)+'\n')
print('Minimized SDK trace artifacts:',len(receipts))
