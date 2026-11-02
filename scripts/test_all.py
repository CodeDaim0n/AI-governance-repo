"""Launch OPA and tests within one process namespace; no skipped integration tests."""
import json
import os
import platform
import re
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path
import cryptography
root=Path(__file__).resolve().parents[1];os.chdir(root);sys.path.insert(0,str(root))
opa=os.environ.get('OPA_BIN','opa')
version=subprocess.check_output([opa,'version'],text=True)
policy=subprocess.run([opa,'test','policies','-v'],capture_output=True,text=True)
Path('results/rego-tests.log').write_text(policy.stdout+policy.stderr)
if policy.returncode:raise SystemExit(policy.returncode)
with open('results/opa.log','w') as log:
 server=subprocess.Popen([opa,'run','--disable-telemetry','--server','--addr=127.0.0.1:8181','policies/credit.rego'],stdout=log,stderr=log)
 try:
  for _ in range(50):
   if server.poll() is not None:raise RuntimeError('OPA startup failed; see results/opa.log')
   try:
    with urllib.request.urlopen('http://127.0.0.1:8181/health',timeout=.2):break
   except Exception:time.sleep(.1)
  else:raise RuntimeError('OPA readiness timeout')
  with open('results/tests.log','w') as f:
   result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.discover('tests'))
  summary={'date':'2026-11-02','python':platform.python_version(),'cryptography':cryptography.__version__,'opa':version,'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'rego_tests':len(re.findall(r': PASS\b',policy.stdout)),'rego_passed':policy.returncode==0,'scope':'Synthetic single-node control and HTTP integration tests; not a model benchmark or product certification'}
  Path('results/summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
  raise SystemExit(not result.wasSuccessful())
 finally:server.terminate();server.wait(timeout=5)
