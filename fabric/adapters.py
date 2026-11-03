"""Explicitly registered transactional adapters for two LOCAL SYNTHETIC targets.

Adapters receive the current database transaction; they must not commit, open a
second transaction or perform network effects. Real external targets need their
own delivery and reconciliation contract and are not supported by these adapters.
"""
from fabric.core import canonical, Rejected


class SyntheticCreditAdapter:
    def validate(self, operation):
        fields = operation['parameters']['properties']
        if set(fields) != {'amount_pence', 'reason'} or set(operation['parameters']['required']) != set(fields) or fields['amount_pence']['type'] != 'integer' or fields['amount_pence']['minimum'] < 1 or fields['reason']['type'] != 'string':
            raise Rejected('adapter_schema_incompatible')

    def apply(self, connection, context):
        action = context['action']
        receipt = {'target': 'local_synthetic_credit_ledger', 'effect_id': context['action_id'],
                   'resource_id': action['resource_id'], 'amount_pence': action['parameters']['amount_pence']}
        connection.execute('INSERT INTO cfg_effects(id,workflow_id,tenant,resource_id,kind,body) VALUES(?,?,?,?,?,?)',
                           (context['action_id'], action['workflow_id'], context['principal']['tenant'], action['resource_id'], 'synthetic_credit', canonical(receipt)))
        return receipt


class SyntheticAccessAdapter:
    def validate(self, operation):
        fields = operation['parameters']['properties']
        if set(fields) != {'permission', 'duration_hours', 'justification'} or set(operation['parameters']['required']) != set(fields) or fields['permission']['type'] != 'string' or fields['duration_hours']['type'] != 'integer' or fields['duration_hours']['minimum'] < 1 or fields['justification']['type'] != 'string':
            raise Rejected('adapter_schema_incompatible')

    def apply(self, connection, context):
        action = context['action']
        receipt = {'target': 'local_synthetic_access_directory', 'effect_id': context['action_id'],
                   'resource_id': action['resource_id'], 'permission': action['parameters']['permission'],
                   'expires_at': context['now'] + action['parameters']['duration_hours'] * 3600}
        connection.execute('INSERT INTO cfg_effects(id,workflow_id,tenant,resource_id,kind,body) VALUES(?,?,?,?,?,?)',
                           (context['action_id'], action['workflow_id'], context['principal']['tenant'], action['resource_id'], 'synthetic_access', canonical(receipt)))
        return receipt


def builtin_adapters():
    """Call explicitly from a trusted deployment entry point to enable demo effects."""
    return {'synthetic-credit': SyntheticCreditAdapter(), 'synthetic-access': SyntheticAccessAdapter()}


def provision_demo(fabric, *, tenant='demo-org'):
    """Explicit local fixture setup. Never call during normal service startup."""
    fixtures = {
        'synthetic-credit': ('case', {'kyc': 'clear', 'region': 'UK'}),
        'it-access': ('employee', {'employee_status': 'active', 'application': 'demo-wiki', 'application_approved': True}),
    }
    if not set(fabric.registry.workflows) <= set(fixtures):
        raise ValueError('demo provisioning supports only the shipped example profiles')
    for suffix, organization in (('a', tenant), ('b', tenant + '-other')):
        for role in ('agent', 'reviewer', 'admin'):
            fabric.provision_principal(role + '-' + suffix, organization, role)
        for workflow_id in fabric.registry.workflows:
            prefix, attributes = fixtures[workflow_id]
            fabric.provision_resource(workflow_id, prefix + '-' + suffix, organization, attributes)
            fabric.approve_workflow(workflow_id, organization, fabric.clock() + 86400)
    return {'tenant': tenant, 'actor': 'agent-a', 'reviewer': 'reviewer-a', 'admin': 'admin-a',
            'resources': {key: value[0] + '-a' for key, value in fixtures.items() if key in fabric.registry.workflows}}
