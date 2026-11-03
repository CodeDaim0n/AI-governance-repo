"""Configuration-driven local transactional governance runtime.

The actor argument and provisioning methods are trusted server boundaries. Never
expose provisioning to agents or derive an actor from action parameters. External
policies can only restrict the built-in checks; configuration approval is explicit.
"""
import contextlib
from decimal import Decimal
import hashlib
import json
import math
import sqlite3
import time
import uuid

from fabric.configuration import ConfigurationError, matches, validate_value
from fabric.core import canonical, digest, Rejected


class _Connection(sqlite3.Connection):
    """The public connection context also closes its file handle on Windows."""
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class ConfigurableFabric:
    SCHEMA = '''
    CREATE TABLE IF NOT EXISTS cfg_principals(id TEXT PRIMARY KEY,tenant TEXT NOT NULL,role TEXT NOT NULL,active INT NOT NULL,version INT NOT NULL);
    CREATE TABLE IF NOT EXISTS cfg_resources(workflow_id TEXT NOT NULL,tenant TEXT NOT NULL,id TEXT NOT NULL,attributes TEXT NOT NULL,version INT NOT NULL,updated REAL NOT NULL,PRIMARY KEY(workflow_id,tenant,id));
    CREATE TABLE IF NOT EXISTS cfg_deployments(workflow_id TEXT NOT NULL,tenant TEXT NOT NULL,config_digest TEXT NOT NULL,version INT NOT NULL,valid_until REAL NOT NULL,PRIMARY KEY(workflow_id,tenant));
    CREATE TABLE IF NOT EXISTS cfg_switches(workflow_id TEXT NOT NULL,tenant TEXT NOT NULL,stopped INT NOT NULL,PRIMARY KEY(workflow_id,tenant));
    CREATE TABLE IF NOT EXISTS cfg_approvals(id TEXT PRIMARY KEY,actor TEXT NOT NULL,reviewer TEXT NOT NULL,reviewer_version INT NOT NULL,hash TEXT NOT NULL,expires REAL NOT NULL,used INT NOT NULL);
    CREATE TABLE IF NOT EXISTS cfg_actions(id TEXT PRIMARY KEY,workflow_id TEXT NOT NULL,actor TEXT NOT NULL,tenant TEXT NOT NULL,idem TEXT NOT NULL,hash TEXT NOT NULL,response TEXT NOT NULL,UNIQUE(workflow_id,actor,tenant,idem));
    CREATE TABLE IF NOT EXISTS cfg_usage(action_id TEXT NOT NULL,workflow_id TEXT NOT NULL,operation TEXT NOT NULL,tenant TEXT NOT NULL,resource_id TEXT NOT NULL,parameter TEXT NOT NULL,amount BIGINT NOT NULL,PRIMARY KEY(action_id,parameter));
    CREATE TABLE IF NOT EXISTS cfg_effects(id TEXT PRIMARY KEY,workflow_id TEXT NOT NULL,tenant TEXT NOT NULL,resource_id TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cfg_audit(seq INTEGER PRIMARY KEY,body TEXT NOT NULL,previous TEXT NOT NULL,hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cfg_outbox(id TEXT PRIMARY KEY,kind TEXT NOT NULL,body TEXT NOT NULL,delivered INT NOT NULL DEFAULT 0);
    '''

    def __init__(self, path, registry, *, adapters=None, policy=None, clock=time.time):
        self.path, self.registry, self.clock, self.policy = str(path), registry, clock, policy
        self.adapters = dict(adapters or {})
        for name, adapter in self.adapters.items():
            if not isinstance(name, str) or not callable(getattr(adapter, 'validate', None)) or not callable(getattr(adapter, 'apply', None)):
                raise ValueError('adapters require explicit validate and transactional apply methods')
        self._initialize()

    def _initialize(self):
        with self.connect() as connection:
            connection.executescript(self.SCHEMA)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None, factory=_Connection)
        connection.row_factory = sqlite3.Row
        return connection

    @contextlib.contextmanager
    def tx(self):
        connection = self.connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _identifier(value):
        return type(value) is str and 1 <= len(value) <= 128 and value.strip() == value and not any(ord(c) < 32 for c in value)

    def principal(self, connection, actor):
        if not self._identifier(actor):
            raise Rejected('identity_inactive')
        row = connection.execute('SELECT * FROM cfg_principals WHERE id=?', (actor,)).fetchone()
        if row is None or not row['active']:
            raise Rejected('identity_inactive')
        return dict(row)

    def provision_principal(self, principal_id, tenant, role, active=True):
        """Trusted administrative API; every update revokes older reviewer approvals."""
        if not all(self._identifier(v) for v in (principal_id, tenant, role)) or type(active) is not bool:
            raise ValueError('invalid principal')
        with self.tx() as c:
            old = c.execute('SELECT version FROM cfg_principals WHERE id=?', (principal_id,)).fetchone()
            version = old['version'] + 1 if old else 1
            c.execute('INSERT INTO cfg_principals(id,tenant,role,active,version) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET tenant=excluded.tenant,role=excluded.role,active=excluded.active,version=excluded.version', (principal_id, tenant, role, int(active), version))
            self.event(c, {'outcome': 'principal_provisioned', 'principal_id': principal_id, 'tenant': tenant, 'version': version})

    def revoke_principal(self, principal_id):
        with self.tx() as c:
            c.execute('UPDATE cfg_principals SET active=0,version=version+1 WHERE id=?', (principal_id,))
            self.event(c, {'outcome': 'principal_revoked', 'principal_id': principal_id})

    def provision_resource(self, workflow_id, resource_id, tenant, attributes, version=1):
        definition = self.registry.get(workflow_id)
        validate_value(attributes, definition.to_dict()['resource_schema'])
        if not all(self._identifier(v) for v in (resource_id, tenant)) or type(version) is not int or version < 1:
            raise ValueError('invalid resource metadata')
        with self.tx() as c:
            old = c.execute('SELECT version FROM cfg_resources WHERE workflow_id=? AND tenant=? AND id=?', (workflow_id, tenant, resource_id)).fetchone()
            if old and version <= old['version']:
                raise ValueError('resource version must increase')
            c.execute('INSERT INTO cfg_resources(workflow_id,tenant,id,attributes,version,updated) VALUES(?,?,?,?,?,?) ON CONFLICT(workflow_id,tenant,id) DO UPDATE SET attributes=excluded.attributes,version=excluded.version,updated=excluded.updated', (workflow_id, tenant, resource_id, canonical(attributes), version, self.clock()))
            self.event(c, {'outcome': 'resource_provisioned', 'workflow_id': workflow_id, 'resource_digest': digest({'workflow_id': workflow_id, 'tenant': tenant, 'resource_id': resource_id}), 'tenant': tenant, 'resource_version': version, 'config_digest': definition.digest})

    def approve_workflow(self, workflow_id, tenant, valid_until):
        """Explicit trusted deployment approval, separate from loading a JSON file."""
        definition = self.registry.get(workflow_id)
        if not self._identifier(tenant) or type(valid_until) not in (int, float) or not math.isfinite(valid_until) or valid_until <= self.clock():
            raise ValueError('invalid deployment approval')
        with self.tx() as c:
            old = c.execute('SELECT version FROM cfg_deployments WHERE workflow_id=? AND tenant=?', (workflow_id, tenant)).fetchone()
            version = old['version'] + 1 if old else 1
            c.execute('INSERT INTO cfg_deployments(workflow_id,tenant,config_digest,version,valid_until) VALUES(?,?,?,?,?) ON CONFLICT(workflow_id,tenant) DO UPDATE SET config_digest=excluded.config_digest,version=excluded.version,valid_until=excluded.valid_until', (workflow_id, tenant, definition.digest, version, valid_until))
            c.execute('INSERT INTO cfg_switches(workflow_id,tenant,stopped) VALUES(?,?,0) ON CONFLICT(workflow_id,tenant) DO NOTHING', (workflow_id, tenant))
            self.event(c, {'outcome': 'workflow_approved', 'workflow_id': workflow_id, 'tenant': tenant, 'config_digest': definition.digest, 'deployment_version': version, 'valid_until': valid_until})

    def provision_demo(self, *, tenant='demo-org'):
        from fabric.adapters import provision_demo
        return provision_demo(self, tenant=tenant)

    def validate(self, action):
        if type(action) is not dict or set(action) != {'workflow_id', 'operation', 'resource_id', 'parameters', 'idempotency_key'}:
            raise Rejected('invalid_schema')
        if not all(self._identifier(action[key]) for key in ('workflow_id', 'operation', 'resource_id', 'idempotency_key')):
            raise Rejected('invalid_schema')
        try:
            definition = self.registry.get(action['workflow_id'])
        except ConfigurationError as exc:
            raise Rejected('unknown_workflow') from exc
        operation = definition.to_dict()['operations'].get(action['operation'])
        if operation is None:
            raise Rejected('unknown_operation')
        try:
            validate_value(action['parameters'], operation['parameters'])
        except (ConfigurationError, TypeError, ValueError) as exc:
            raise Rejected('invalid_parameters') from exc
        return definition

    def _snapshot_action(self, action):
        try:
            snapshot = json.loads(canonical(action))
        except (TypeError, ValueError, RecursionError) as exc:
            raise Rejected('invalid_schema') from exc
        return snapshot, self.validate(snapshot)

    def _resource(self, c, principal, definition, resource_id):
        row = c.execute('SELECT * FROM cfg_resources WHERE workflow_id=? AND tenant=? AND id=?', (definition.workflow_id, principal['tenant'], resource_id)).fetchone()
        if not row:
            raise Rejected('resource_unavailable')
        resource = dict(row)
        resource['attributes'] = json.loads(resource['attributes'])
        try:
            validate_value(resource['attributes'], definition.to_dict()['resource_schema'])
        except ConfigurationError as exc:
            raise Rejected('resource_schema_changed') from exc
        if not 0 <= self.clock() - resource['updated'] <= definition.to_dict()['resource_freshness_seconds']:
            raise Rejected('resource_stale')
        return resource

    def _deployment(self, c, definition, tenant):
        deployment = c.execute('SELECT * FROM cfg_deployments WHERE workflow_id=? AND tenant=?', (definition.workflow_id, tenant)).fetchone()
        if not deployment or deployment['config_digest'] != definition.digest or deployment['valid_until'] <= self.clock():
            raise Rejected('workflow_unapproved')
        switch = c.execute('SELECT stopped FROM cfg_switches WHERE workflow_id=? AND tenant=?', (definition.workflow_id, tenant)).fetchone()
        if not switch or switch['stopped']:
            raise Rejected('workflow_stopped')
        return dict(deployment)

    @staticmethod
    def _budget_total(value):
        # PostgreSQL SUM(BIGINT) returns NUMERIC/Decimal; SQLite returns int.
        # Keep the shared policy/adapter context JSON-native without rounding or
        # accepting fractional, nonfinite, negative, or coercible string totals.
        if type(value) is Decimal:
            if not value.is_finite() or value != value.to_integral_value():
                raise Rejected('invalid_budget_usage')
            value = int(value)
        if type(value) is not int or value < 0:
            raise Rejected('invalid_budget_usage')
        return value

    def context(self, c, actor, action, definition):
        p = self.principal(c, actor)
        workflow = definition.to_dict()
        operation = workflow['operations'][action['operation']]
        resource = self._resource(c, p, definition, action['resource_id'])
        deployment = self._deployment(c, definition, p['tenant'])
        if p['role'] not in operation['allowed_roles']:
            raise Rejected('operation_authority')
        if not all(matches(check, resource['attributes']) for check in operation['resource_checks']):
            raise Rejected('resource_policy_denied')
        adapter = self.adapters.get(operation['adapter'])
        if adapter is None:
            raise Rejected('adapter_unavailable')
        try:
            adapter.validate(operation)
        except Rejected:
            raise
        except Exception as exc:
            raise Rejected('adapter_schema_incompatible') from exc
        budgets = []
        for budget in operation['budgets']:
            sql = 'SELECT COALESCE(SUM(amount),0) AS spent FROM cfg_usage WHERE workflow_id=? AND operation=? AND tenant=? AND parameter=?'
            args = [action['workflow_id'], action['operation'], p['tenant'], budget['parameter']]
            if budget['scope'] == 'resource':
                sql += ' AND resource_id=?'
                args.append(action['resource_id'])
            spent = self._budget_total(c.execute(sql, tuple(args)).fetchone()['spent'])
            requested = action['parameters'][budget['parameter']]
            if spent + requested > budget['limit']:
                raise Rejected('budget_exceeded')
            budgets.append({**budget, 'spent': spent, 'requested': requested})
        return {'principal': p, 'action': action, 'resource': resource, 'workflow': workflow,
                'config_digest': definition.digest, 'deployment': deployment, 'now': self.clock(), 'approved': False, 'budgets': budgets}

    @staticmethod
    def bound_hash(ctx):
        return digest({'action': ctx['action'], 'principal': ctx['principal'], 'resource': ctx['resource'],
                       'config_digest': ctx['config_digest'], 'deployment': ctx['deployment']})

    def _policy(self, ctx):
        if self.policy is None:
            return
        try:
            result = self.policy.decide(json.loads(canonical(ctx)))
        except Exception as exc:
            raise Rejected('policy_unavailable') from exc
        if type(result) is not dict or result.get('allow') is not True:
            raise Rejected('external_policy_denied')

    def approve(self, reviewer, actor, action):
        action, definition = self._snapshot_action(action)
        with self.tx() as c:
            ctx = self.context(c, actor, action, definition)
            r = self.principal(c, reviewer)
            settings = ctx['workflow']['operations'][action['operation']]['approval']
            if reviewer == actor or r['tenant'] != ctx['principal']['tenant'] or r['role'] not in settings['reviewer_roles']:
                raise Rejected('approval_authority')
            ctx['approved'] = True
            self._policy(ctx)
            # External authorities can block long enough for source or deployment
            # validity to expire; issuance uses current local authority.
            ctx = self.context(c, actor, action, definition)
            ctx['approved'] = True
            approval_id = str(uuid.uuid4())
            c.execute('INSERT INTO cfg_approvals(id,actor,reviewer,reviewer_version,hash,expires,used) VALUES(?,?,?,?,?,?,0)',
                      (approval_id, actor, reviewer, r['version'], self.bound_hash(ctx), self.clock() + settings['ttl_seconds']))
            self.event(c, {'actor': reviewer, 'tenant': r['tenant'], 'outcome': 'approved', 'approval_id': approval_id,
                           'workflow_id': action['workflow_id'], 'action_hash': self.bound_hash(ctx), 'config_digest': definition.digest})
            return approval_id

    def _approval(self, c, ctx, approval_id):
        if approval_id is None:
            return False
        if not self._identifier(approval_id):
            return False
        row = c.execute('SELECT * FROM cfg_approvals WHERE id=?', (approval_id,)).fetchone()
        if not row or row['used'] or row['expires'] <= self.clock() or row['actor'] != ctx['principal']['id'] or row['hash'] != self.bound_hash(ctx):
            return False
        try:
            reviewer = self.principal(c, row['reviewer'])
        except Rejected:
            return False
        settings = ctx['workflow']['operations'][ctx['action']['operation']]['approval']
        return bool(reviewer['id'] != ctx['principal']['id'] and reviewer['tenant'] == ctx['principal']['tenant'] and
                    reviewer['role'] in settings['reviewer_roles'] and reviewer['version'] == row['reviewer_version'])

    def execute(self, actor, action, approval_id=None, *, precondition=None):
        """Execute under the storage guard.

        An operator-supplied precondition(connection) may revalidate a server
        task binding under the same guard, initially and after external policy
        calls. It must be repeatable trusted application code, never configuration
        or an action-provided callback.
        """
        # Snapshot caller-owned mutable data before validation and hashing.
        action, definition = self._snapshot_action(action)
        with self.tx() as c:
            if precondition is not None:
                precondition(c)
            p = self.principal(c, actor)
            old = c.execute('SELECT * FROM cfg_actions WHERE workflow_id=? AND actor=? AND tenant=? AND idem=?',
                            (action['workflow_id'], actor, p['tenant'], action['idempotency_key'])).fetchone()
            if old:
                if old['hash'] != digest(action):
                    raise Rejected('idempotency_conflict')
                # This returns historical evidence; it never repeats the effect.
                return json.loads(old['response'])
            c.execute('SAVEPOINT governed_effect')
            try:
                ctx = self.context(c, actor, action, definition)
                operation = ctx['workflow']['operations'][action['operation']]
                ctx['approved'] = self._approval(c, ctx, approval_id)
                requires_approval = any(matches(condition, action['parameters']) for condition in operation['approval']['when'])
                if requires_approval and not ctx['approved']:
                    raise Rejected('approval_required')
                self._policy(ctx)
                if precondition is not None:
                    precondition(c)
                # Time may advance during a remote policy decision even while
                # the storage guard prevents concurrent local authority changes.
                previously_approved = ctx['approved']
                ctx = self.context(c, actor, action, definition)
                ctx['approved'] = self._approval(c, ctx, approval_id)
                if (requires_approval or previously_approved) and not ctx['approved']:
                    raise Rejected('approval_required')
                ctx['action_id'] = str(uuid.uuid4())
                try:
                    receipt = self.adapters[operation['adapter']].apply(c, json.loads(canonical(ctx)))
                    if type(receipt) is not dict or not receipt:
                        raise ValueError('adapter receipt must be a nonempty object')
                    canonical(receipt)
                except Exception as exc:
                    raise Rejected('adapter_failed') from exc
                response = {'status': 'executed', 'action_id': ctx['action_id'], 'workflow_id': action['workflow_id'],
                            'config_digest': definition.digest, 'workflow_version': definition.version, 'receipt': receipt}
                c.execute('INSERT INTO cfg_actions(id,workflow_id,actor,tenant,idem,hash,response) VALUES(?,?,?,?,?,?,?)',
                          (ctx['action_id'], action['workflow_id'], actor, p['tenant'], action['idempotency_key'], digest(action), canonical(response)))
                # Preserve positive numeric usage even before a budget is added in
                # a later approved configuration revision.
                for parameter in sorted(key for key, value in action['parameters'].items() if type(value) is int and value > 0):
                    c.execute('INSERT INTO cfg_usage(action_id,workflow_id,operation,tenant,resource_id,parameter,amount) VALUES(?,?,?,?,?,?,?)',
                              (ctx['action_id'], action['workflow_id'], action['operation'], p['tenant'], action['resource_id'], parameter, action['parameters'][parameter]))
                if ctx['approved']:
                    c.execute('UPDATE cfg_approvals SET used=1 WHERE id=?', (approval_id,))
                self.event(c, {'actor': actor, 'tenant': p['tenant'], 'workflow_id': action['workflow_id'], 'outcome': 'executed',
                               'action_hash': digest(action), 'action_id': ctx['action_id'], 'resource_digest': digest({'workflow_id': action['workflow_id'], 'tenant': p['tenant'], 'resource_id': action['resource_id']}),
                               'resource_version': ctx['resource']['version'], 'config_digest': definition.digest, 'receipt_digest': digest(receipt)})
                c.execute('RELEASE SAVEPOINT governed_effect')
                return response
            except Rejected as exc:
                c.execute('ROLLBACK TO SAVEPOINT governed_effect')
                c.execute('RELEASE SAVEPOINT governed_effect')
                self.event(c, {'actor': actor, 'tenant': p['tenant'], 'workflow_id': action['workflow_id'], 'outcome': 'denied',
                               'action_hash': digest(action), 'reason': str(exc), 'config_digest': definition.digest})
                return {'status': 'denied', 'reason': str(exc)}

    def inspect(self, actor, workflow_id, resource_id):
        if not self._identifier(resource_id):
            raise Rejected('invalid_schema')
        try:
            definition = self.registry.get(workflow_id)
        except ConfigurationError as exc:
            raise Rejected('unknown_workflow') from exc
        with self.tx() as c:
            p = self.principal(c, actor)
            self._deployment(c, definition, p['tenant'])
            roles = {role for operation in definition.to_dict()['operations'].values() for role in operation['allowed_roles'] + operation['approval']['reviewer_roles']}
            if p['role'] not in roles:
                raise Rejected('inspection_authority')
            resource = self._resource(c, p, definition, resource_id)
            if self.policy is not None:
                try:
                    result = self.policy.authorize_read(p, json.loads(canonical(resource)), definition)
                except Exception as exc:
                    raise Rejected('read_policy_unavailable') from exc
                if result is not True and not (type(result) is dict and result.get('allow') is True):
                    raise Rejected('external_read_policy_denied')
                # A remote read gate can outlast the local validity window.
                self._deployment(c, definition, p['tenant'])
                resource = self._resource(c, p, definition, resource_id)
            self.event(c, {'actor': actor, 'tenant': p['tenant'], 'outcome': 'inspected', 'workflow_id': workflow_id, 'resource_digest': digest({'workflow_id': workflow_id, 'tenant': p['tenant'], 'resource_id': resource_id}), 'config_digest': definition.digest})
            return {**resource, 'resource_id': resource['id'], 'config_digest': definition.digest, 'workflow_version': definition.version}

    def stop(self, actor, workflow_id, stopped=True):
        if type(stopped) is not bool:
            raise Rejected('invalid_schema')
        try:
            definition = self.registry.get(workflow_id)
        except ConfigurationError as exc:
            raise Rejected('unknown_workflow') from exc
        with self.tx() as c:
            p = self.principal(c, actor)
            if p['role'] != 'admin':
                raise Rejected('admin_required')
            c.execute('INSERT INTO cfg_switches(workflow_id,tenant,stopped) VALUES(?,?,?) ON CONFLICT(workflow_id,tenant) DO UPDATE SET stopped=excluded.stopped', (workflow_id, p['tenant'], int(stopped)))
            self.event(c, {'actor': actor, 'tenant': p['tenant'], 'workflow_id': workflow_id, 'outcome': 'stopped' if stopped else 'resumed', 'config_digest': definition.digest})

    def event(self, c, event):
        previous = c.execute('SELECT hash FROM cfg_audit ORDER BY seq DESC LIMIT 1').fetchone()
        previous = previous['hash'] if previous else '0' * 64
        body = canonical({'time': self.clock(), **event})
        event_hash = hashlib.sha256((previous + body).encode()).hexdigest()
        c.execute('INSERT INTO cfg_audit(body,previous,hash) VALUES(?,?,?)', (body, previous, event_hash))
        event_id = str(uuid.uuid4())
        c.execute('INSERT INTO cfg_outbox(id,kind,body) VALUES(?,?,?)', (event_id, 'evidence', body))
        if event.get('outcome') == 'denied':
            c.execute('INSERT INTO cfg_outbox(id,kind,body) VALUES(?,?,?)', (str(uuid.uuid4()), 'incident', canonical({'event_id': event_id, 'workflow_id': event.get('workflow_id'), 'reason': event['reason']})))

    def verify_chain(self):
        previous = '0' * 64
        with self.connect() as c:
            for row in c.execute('SELECT * FROM cfg_audit ORDER BY seq'):
                if row['previous'] != previous or row['hash'] != hashlib.sha256((previous + row['body']).encode()).hexdigest():
                    return False
                previous = row['hash']
        return True
