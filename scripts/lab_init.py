import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fabric.core import Fabric
p=Path('.local');p.mkdir(exist_ok=True)
if not (p/'private.pem').exists():
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
 fd=os.open(p/'private.pem',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f: f.write(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
 (p/'public.pem').write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
Fabric(p/'lab.db').seed()
print('Synthetic lab initialized; reseeding refreshes evidence, never use against production.')
