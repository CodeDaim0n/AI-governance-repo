"""Optional Microsoft AGT 5.0 wrapper. Gateway remains the final authority.
AGT wrapper alone is bypassable by same-process code; isolate the remote gateway.
"""
from .core import Rejected

def wrap(fabric, authenticated_actor):
    from agentmesh.governance import govern
    policy='''apiVersion: governance.toolkit/v1
name: fabric-tool-boundary
version: "1.0"
default_action: deny
rules:
  - name: permit-credit-proposal
    condition: "action.type == 'credit.commit'"
    action: allow
'''
    def call(*,action,proposal,approval_id=None):
        if action!=proposal.get('tool'):raise Rejected('tool_binding_mismatch')
        return fabric.execute(authenticated_actor,proposal,approval_id)
    return govern(call,policy=policy,agent_id=authenticated_actor,audit=True)
