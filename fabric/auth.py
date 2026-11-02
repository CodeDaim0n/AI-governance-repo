"""Narrow RS256 lab token profile. Keycloak integration needs JWKS rotation.
No self-supplied keys, algorithm negotiation or unverified identity headers.
"""
import base64
import json
import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from .core import Rejected, canonical

def b64(v): return base64.urlsafe_b64encode(v).rstrip(b'=').decode()
def unb64(v): return base64.urlsafe_b64decode(v + '='*(-len(v)%4))
def issue(private_pem, sub, lifetime=300, **overrides):
    claims={'sub':sub,'iss':'fabric-lab','aud':'fabric-gateway','iat':int(time.time()),'exp':int(time.time())+lifetime,**overrides}
    msg=b64(canonical({'alg':'RS256','typ':'JWT'}).encode())+'.'+b64(canonical(claims).encode())
    key=serialization.load_pem_private_key(private_pem,password=None)
    sig=key.sign(msg.encode(),padding.PKCS1v15(),hashes.SHA256())
    return msg+'.'+b64(sig)
def verify(public_pem, token, now=None):
    try:
        if len(token)>8192: raise ValueError()
        h,p,s=token.split('.')
        header=json.loads(unb64(h))
        if header != {'alg':'RS256','typ':'JWT'}: raise ValueError()
        key=serialization.load_pem_public_key(public_pem)
        key.verify(unb64(s),(h+'.'+p).encode(),padding.PKCS1v15(),hashes.SHA256())
        c=json.loads(unb64(p)); now=time.time() if now is None else now
        if c['iss']!='fabric-lab' or c['aud']!='fabric-gateway' or type(c['exp']) is not int or type(c['iat']) is not int or not c['iat']<=now<c['exp'] or not isinstance(c['sub'],str): raise ValueError()
        return c['sub']
    except Exception as e: raise Rejected('invalid_token') from e
