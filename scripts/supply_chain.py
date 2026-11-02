"""Execute Syft, Grype and Cosign; never report a pass from tool presence alone."""
import json,os,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[1];L=R/'.local/full/supply-chain';L.mkdir(parents=True,exist_ok=True)
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def main():
 # Scan the built native image, not a directory that omits installed packages.
 image=os.environ.get('FABRIC_IMAGE','fabric-native-gateway:latest')
 sbom=L/'sbom.spdx.json'
 with sbom.open('w') as f:run(['syft',image,'-o','spdx-json'],stdout=f)
 report=L/'vulnerabilities.json'
 with report.open('w') as f:run(['grype','sbom:'+str(sbom),'-o','json','--fail-on','high'],stdout=f)
 # Local offline signing, no OIDC flow or transparency-service dependency.
 # Protect the generated private key and its passphrase outside production agents.
 if not os.environ.get('COSIGN_PASSWORD'):raise SystemExit('Set a private COSIGN_PASSWORD; never store it in Git')
 key=L/'cosign.key';pub=L/'cosign.pub';sig=L/'sbom.sig';bundle=L/'sbom.bundle'
 if not key.exists():run(['cosign','generate-key-pair','--output-key-prefix',str(L/'cosign')])
 run(['cosign','sign-blob','--yes','--tlog-upload=false','--key',str(key),'--output-signature',str(sig),'--output-bundle',str(bundle),str(sbom)])
 run(['cosign','verify-blob','--key',str(pub),'--signature',str(sig),'--insecure-ignore-tlog',str(sbom)])
 (R/'results/supply-chain-live.json').write_text(json.dumps({'deployment_id':(R/'.local/full/deployment-id').read_text().strip(),'source_commit':subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip(),'component':'17 Syft Grype Cosign','sbom':'generated from built native image','vulnerability_gate':'high and critical rejected','signature':'verified using local public key','transparency_log':'not used; offline lab signature only'},indent=2))
 print('SBOM generated, vulnerability gate passed, offline signature verified.')
if __name__=='__main__':main()
