"""Optional Microsoft AGT 5.0 wrapper. Gateway remains the final authority.
AGT wrapper alone is bypassable by same-process code; isolate the remote gateway.
"""
from .core import Rejected


def install_configurable(fabric):
    """Attach AGT interception using operator-loaded operation definitions.

    The independent gateway checks remain authoritative. This in-process wrapper
    does not replace network isolation or protect against hostile host code.
    """
    import json
    from agentmesh.governance import govern, GovernanceDenied
    original_execute = fabric.execute

    def execute(actor, proposal, approval_id=None, *, precondition=None):
        fabric.validate(proposal)
        operation_id = proposal['workflow_id'] + '.' + proposal['operation']
        rules = []
        for definition in fabric.registry.workflows.values():
            for name in definition.to_dict()['operations']:
                tool = definition.workflow_id + '.' + name
                rules.append({'name': 'permit-' + tool, 'condition': "action.type == '" + tool + "'", 'action': 'allow'})
        policy = json.dumps({'apiVersion': 'governance.toolkit/v1', 'name': 'configured-operation-boundary',
                             'version': '1.0', 'default_action': 'deny', 'rules': rules})

        def call(*, action, proposal, approval_id=None):
            if action != proposal['workflow_id'] + '.' + proposal['operation']:
                raise Rejected('tool_binding_mismatch')
            return original_execute(actor, proposal, approval_id, precondition=precondition)

        tool = govern(call, policy=policy, agent_id=actor, audit=True)
        try:
            return tool(action=operation_id, proposal=proposal, approval_id=approval_id)
        except GovernanceDenied as exc:
            raise Rejected('tool_not_allowed') from exc

    fabric.execute = execute
    return fabric

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
