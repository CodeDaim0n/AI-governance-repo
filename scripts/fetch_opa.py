"""Fetch the exact historical research binary; verify the recorded artifact digest.
This pins observed bytes, not independent upstream release provenance.
"""
import hashlib,os,platform,urllib.request
from pathlib import Path
if platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64'):
 raise SystemExit('This helper supports Linux amd64 only; obtain OPA from its official project for your platform.')
url='https://openpolicyagent.org/downloads/v1.0.1/opa_linux_amd64_static'
expected='6d81be862e412af910eacfad489e3d77afbfcf4b958ea4e839b7f38c9eec4d87'
root=Path(__file__).resolve().parents[1];dest=root/'.local'/'opa';dest.parent.mkdir(exist_ok=True)
with urllib.request.urlopen(url,timeout=60) as response:data=response.read()
if hashlib.sha256(data).hexdigest()!=expected:raise SystemExit('OPA digest mismatch: review the release; do not bypass verification')
dest.write_bytes(data);dest.chmod(0o700);print(dest)
