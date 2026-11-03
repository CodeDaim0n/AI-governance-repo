"""Check the configurable runtime against caller-provided real PostgreSQL.

This creates uniquely scoped synthetic fixtures and leaves them for restart checks.
It neither starts services nor deletes existing data. PostgreSQL storage success
is not evidence of native OPA, identity, model, or eighteen-component acceptance.
Prefer DATABASE_URL over putting a credential-bearing DSN on the command line.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fabric.adapters import builtin_adapters
from fabric.configuration import WorkflowRegistry


def registry():
    return WorkflowRegistry.from_paths([
        ROOT / 'workflows/synthetic-credit.json', ROOT / 'workflows/it-access.json',
    ])


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def effect_count(fabric, tenant, *, workflow_id=None, resource_id=None):
    sql = 'SELECT COUNT(*) AS count FROM cfg_effects WHERE tenant=?'
    values = [tenant]
    if workflow_id is not None:
        sql += ' AND workflow_id=?'
        values.append(workflow_id)
    if resource_id is not None:
        sql += ' AND resource_id=?'
        values.append(resource_id)
    with fabric.connect() as connection:
        return connection.execute(sql, tuple(values)).fetchone()['count']


def _exercise(fabric, run_id):
    """Backend-neutral scenarios; only run() labels verified PostgreSQL evidence."""
    tenant = 'acceptance-' + run_id
    actor, other_actor = 'agent-' + run_id, 'agent2-' + run_id
    reviewer = 'reviewer-' + run_id
    resource_credit, resource_access, resource_budget = ('credit-' + run_id, 'access-' + run_id, 'budget-' + run_id)
    for principal, role in ((actor, 'agent'), (other_actor, 'agent'), (reviewer, 'reviewer')):
        fabric.provision_principal(principal, tenant, role)
    for resource in (resource_credit, resource_budget):
        fabric.provision_resource('synthetic-credit', resource, tenant, {'kyc': 'clear', 'region': 'UK'})
    fabric.provision_resource('it-access', resource_access, tenant,
                             {'employee_status': 'active', 'application': 'acceptance-wiki', 'application_approved': True})
    for workflow_id in fabric.registry.workflows:
        fabric.approve_workflow(workflow_id, tenant, fabric.clock() + 3600)

    def credit(amount, key, resource=resource_credit):
        return {'workflow_id': 'synthetic-credit', 'operation': 'commit_credit', 'resource_id': resource,
                'parameters': {'amount_pence': amount, 'reason': 'Synthetic PostgreSQL acceptance'},
                'idempotency_key': key}

    actions = [credit(20000, 'approval-credit'),
               {'workflow_id': 'it-access', 'operation': 'grant_access', 'resource_id': resource_access,
                'parameters': {'permission': 'admin', 'duration_hours': 4, 'justification': 'Synthetic PostgreSQL acceptance'},
                'idempotency_key': 'approval-access'}]
    checks, restart_replays = {}, []
    journeys = []
    for action in actions:
        denied = fabric.execute(actor, action)
        require(denied == {'status': 'denied', 'reason': 'approval_required'}, 'An effect escaped its independent approval gate')
        require(effect_count(fabric, tenant, workflow_id=action['workflow_id']) == 0, 'Denied journey wrote an effect')
        approval_id = fabric.approve(reviewer, actor, action)
        response = fabric.execute(actor, action, approval_id)
        require(response.get('status') == 'executed', 'Approved journey did not execute: ' + str(response.get('reason', 'missing_reason')))
        require(response.get('config_digest') == fabric.registry.get(action['workflow_id']).digest, 'Receipt configuration binding is wrong')
        require(response.get('receipt', {}).get('effect_id') == response['action_id'], 'Receipt is not bound to its target effect')
        repeated = fabric.execute(actor, action, approval_id)
        require(repeated == response, 'Retry did not return the exact persisted receipt')
        require(effect_count(fabric, tenant, workflow_id=action['workflow_id']) == 1, 'Approved journey created duplicate effects')
        restart_replays.append({'actor': actor, 'action': action, 'response': response})
        journeys.append({'workflow_id': action['workflow_id'], 'denied_before_approval': True,
                         'config_digest': response['config_digest'], 'receipt': response['receipt'],
                         'retry_returns_same_receipt': True})
    checks['two_configured_approval_journeys'] = journeys

    substitution = credit(20000, 'substitution')
    approval_id = fabric.approve(reviewer, actor, substitution)
    changed = {**substitution, 'parameters': {**substitution['parameters'], 'amount_pence': 20001}}
    result = fabric.execute(actor, changed, approval_id)
    require(result == {'status': 'denied', 'reason': 'approval_required'}, 'Substituted action reused an approval')
    require(effect_count(fabric, tenant) == 2, 'Approval substitution created an effect')
    checks['approval_substitution_denied'] = True

    duplicate = credit(1000, 'concurrent-duplicate')
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(lambda _: fabric.execute(actor, duplicate), range(12)))
    require(all(response == responses[0] and response.get('status') == 'executed' for response in responses),
            'Concurrent retries did not converge on one persisted receipt')
    require(effect_count(fabric, tenant, resource_id=resource_credit) == 2, 'Concurrent duplicate created more than one additional effect')
    restart_replays.append({'actor': actor, 'action': duplicate, 'response': responses[0]})
    checks['concurrent_duplicate_one_effect'] = {'requests': 12, 'additional_effects': 1}

    def spend(index):
        return fabric.execute(actor if index % 2 else other_actor, credit(10000, 'budget-' + str(index), resource_budget))

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(spend, range(15)))
    executed = sum(response.get('status') == 'executed' for response in responses)
    denied = sum(response == {'status': 'denied', 'reason': 'budget_exceeded'} for response in responses)
    require((executed, denied) == (10, 5), 'Concurrent actors did not share the resource budget atomically')
    require(effect_count(fabric, tenant, resource_id=resource_budget) == 10, 'Budget race wrote an incorrect number of effects')
    with fabric.connect() as connection:
        spent = connection.execute('SELECT COALESCE(SUM(amount),0) AS spent FROM cfg_usage WHERE tenant=? AND resource_id=? AND parameter=?',
                                   (tenant, resource_budget, 'amount_pence')).fetchone()['spent']
    require(spent == 100000, 'Persisted usage differs from the aggregate resource budget')
    spent = int(spent)  # PostgreSQL SUM(BIGINT) returns Decimal; evidence is JSON.
    checks['shared_resource_budget_race'] = {'actors': 2, 'requests': 15, 'executed': executed, 'denied': denied, 'spent': spent}

    original_registry = fabric.registry
    revised = original_registry.get('synthetic-credit').to_dict()
    revised['version'] = 'credit-acceptance-revision'
    fabric.registry = WorkflowRegistry([revised, original_registry.get('it-access')])
    try:
        result = fabric.execute(actor, credit(1, 'unapproved-revision'))
        require(result == {'status': 'denied', 'reason': 'workflow_unapproved'}, 'Changed configuration reused deployment approval')
    finally:
        fabric.registry = original_registry
    checks['changed_configuration_denied'] = True

    expected_effects = 13
    require(effect_count(fabric, tenant) == expected_effects, 'Unexpected final effect count')
    require(fabric.verify_chain(), 'Persisted audit chain failed verification')
    with fabric.connect() as connection:
        rows = connection.execute('SELECT body FROM cfg_audit ORDER BY seq').fetchall()
        events = [json.loads(row['body']) for row in rows]
        executed_events = [event for event in events if event.get('tenant') == tenant and event.get('outcome') == 'executed']
        for event in executed_events:
            require(event.get('config_digest') == original_registry.get(event['workflow_id']).digest, 'Audit event lost its configuration binding')
            require('receipt_digest' in event and 'receipt' not in event, 'Audit receipt minimization failed')
        outbox_rows = connection.execute('SELECT body FROM cfg_outbox WHERE kind=?', ('evidence',)).fetchall()
        queued_events = [json.loads(row['body']) for row in outbox_rows]
        queued_actions = {event['action_id'] for event in queued_events
                          if event.get('tenant') == tenant and event.get('outcome') == 'executed'}
    require(len(executed_events) == expected_effects, 'Effects and audited executions differ')
    require(queued_actions == {event['action_id'] for event in executed_events}, 'Audited effects and evidence outbox differ')
    checks['audit_integrity_and_config_binding'] = {'chain_valid': True, 'executed_events': len(executed_events), 'outbox_effects': len(queued_actions)}
    return {'fixture': {'tenant': tenant, 'actors': [actor, other_actor], 'reviewer': reviewer},
            'expected_effect_count': expected_effects, 'checks': checks, 'restart_replays': restart_replays}


def run(dsn):
    """Return evidence only after actual PostgreSQL queries and all checks pass."""
    from fabric.enterprise.configurable import ConfigurablePostgresFabric
    if not isinstance(dsn, str) or not dsn:
        raise ValueError('A caller-provided PostgreSQL DSN is required')
    fabric = ConfigurablePostgresFabric(dsn, registry(), adapters=builtin_adapters())
    with fabric.connect() as connection:
        server_version = connection.execute('SELECT version() AS version').fetchone()['version']
        encoding = connection.execute('SHOW server_encoding').fetchone()[0]
    require(isinstance(server_version, str) and server_version.startswith('PostgreSQL '), 'Database did not identify itself as PostgreSQL')
    require(encoding == 'UTF8', 'PostgreSQL acceptance requires UTF8 text decoding')
    result = _exercise(fabric, uuid.uuid4().hex[:16])
    return {'status': 'PASS', 'scope': 'Real PostgreSQL storage with synthetic local targets; no model or other native-service acceptance',
            'postgres_version': server_version, 'server_encoding': encoding, **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dsn', default=os.environ.get('DATABASE_URL'), help='Defaults to DATABASE_URL; prefer the environment for credentials')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.dsn:
        parser.error('Supply DATABASE_URL or --dsn')
    result = run(args.dsn)
    output = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding='utf-8')
    print(output, end='')


if __name__ == '__main__':
    main()
