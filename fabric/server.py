"""Loopback-only HTTP facade; TLS and ingress controls are deployment requirements."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .auth import verify
from .core import Fabric, Rejected

def make_handler(fabric, public_key):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass  # Never put tokens or body in access logs.
        def do_POST(self):
            try:
                auth=self.headers.get('Authorization','')
                if not auth.startswith('Bearer '): raise Rejected('token_required')
                actor=verify(public_key,auth[7:])
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=16384: raise Rejected('body_size')
                body=json.loads(self.rfile.read(n))
                if self.path=='/execute': result=fabric.execute(actor,body['action'],body.get('approval_id'))
                elif self.path=='/approve': result={'approval_id':fabric.approve(actor,body['actor'],body['action'])}
                elif self.path=='/stop':
                    if type(body.get('stopped')) is not bool: raise Rejected('invalid_schema')
                    fabric.stop(actor,body['stopped']);result={'status':'updated'}
                else: raise Rejected('route_not_allowed')
                self.reply(200,result)
            except Rejected as e: self.reply(403,{'error':str(e)})
            except (ValueError,KeyError,TypeError): self.reply(400,{'error':'invalid_request'})
            except Exception: self.reply(503,{'error':'dependency_or_storage_unavailable'})
        def reply(self,status,value):
            data=json.dumps(value).encode();self.send_response(status)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    return Handler

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--public-key',required=True);p.add_argument('--port',type=int,default=8088);a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),make_handler(Fabric(a.db),Path(a.public_key).read_bytes()))
    server.serve_forever()
if __name__=='__main__': main()
