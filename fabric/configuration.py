"""Strict, versioned workflow contracts. Definitions never select Python code or URLs."""
from dataclasses import dataclass
import json
import re
from types import MappingProxyType

from fabric.core import canonical, digest


class ConfigurationError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise ConfigurationError(message)


def _keys(value, required, optional=()):
    _require(type(value) is dict, 'expected object')
    _require(set(required) <= set(value) <= set(required) | set(optional), 'unknown or missing fields')


def _name(value):
    return type(value) is str and re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value) is not None


def _strings(value):
    return type(value) is list and bool(value) and all(_name(v) for v in value) and len(set(value)) == len(value)


def validate_value(value, schema):
    """Validate the deliberately bounded schema vocabulary, without coercion."""
    kind = schema['type']
    expected = {'string': str, 'integer': int, 'boolean': bool, 'object': dict}[kind]
    if type(value) is not expected:
        raise ConfigurationError('wrong value type')
    if kind == 'object':
        if not set(schema['required']) <= set(value) <= set(schema['properties']):
            raise ConfigurationError('unknown or missing properties')
        for key, item in value.items():
            validate_value(item, schema['properties'][key])
    elif kind == 'string':
        if not schema['minLength'] <= len(value) <= schema['maxLength']:
            raise ConfigurationError('string length out of bounds')
    elif kind == 'integer':
        if not schema['minimum'] <= value <= schema['maximum']:
            raise ConfigurationError('integer out of bounds')
    if 'enum' in schema and not any(type(value) is type(item) and value == item for item in schema['enum']):
        raise ConfigurationError('value outside enum')


def _schema(schema, *, object_root=False):
    _require(type(schema) is dict, 'schema must be an object')
    kind = schema.get('type')
    _require(kind in ('string', 'integer', 'boolean', 'object'), 'unsupported schema type')
    if object_root:
        _require(kind == 'object', 'root schema must be object')
    if kind == 'object':
        _keys(schema, ('type', 'properties', 'required', 'additionalProperties'))
        _require(schema['additionalProperties'] is False, 'additional properties must be disabled')
        props, required = schema['properties'], schema['required']
        _require(type(props) is dict and 1 <= len(props) <= 32 and all(_name(k) for k in props), 'invalid properties')
        _require(type(required) is list and all(type(k) is str for k in required) and len(required) == len(set(required)) and set(required) <= set(props), 'invalid required fields')
        for value in props.values():
            _require(type(value) is dict and value.get('type') != 'object', 'only primitive properties are supported')
            _schema(value)
    elif kind == 'string':
        _keys(schema, ('type', 'minLength', 'maxLength'), ('enum',))
        _require(type(schema['minLength']) is int and type(schema['maxLength']) is int and 0 <= schema['minLength'] <= schema['maxLength'] <= 8192, 'invalid string limits')
    elif kind == 'integer':
        _keys(schema, ('type', 'minimum', 'maximum'), ('enum',))
        _require(type(schema['minimum']) is int and type(schema['maximum']) is int and -(2**53) <= schema['minimum'] <= schema['maximum'] <= 2**53, 'invalid integer limits')
    else:
        _keys(schema, ('type',), ('enum',))
    if 'enum' in schema:
        values = schema['enum']
        _require(type(values) is list and 1 <= len(values) <= 64, 'invalid enum')
        _require(len({canonical(v) for v in values}) == len(values), 'duplicate enum')
        for value in values:
            validate_value(value, {k: v for k, v in schema.items() if k != 'enum'})


def _conditions(conditions, schema):
    _require(type(conditions) is list and len(conditions) <= 32, 'invalid conditions')
    for condition in conditions:
        _keys(condition, ('field', 'op', 'value'))
        field, op, value = condition['field'], condition['op'], condition['value']
        _require(type(field) is str and field in schema['required'], 'condition field must be required')
        _require(op in ('eq', 'ne', 'in', 'not_in', 'gt', 'gte', 'lt', 'lte'), 'unsupported predicate')
        field_schema = schema['properties'][field]
        if op in ('gt', 'gte', 'lt', 'lte'):
            _require(field_schema['type'] == 'integer', 'ordered predicate requires integer')
        values = value if op in ('in', 'not_in') else [value]
        _require(type(values) is list and 1 <= len(values) <= 64, 'invalid predicate values')
        for item in values:
            validate_value(item, field_schema)


def matches(condition, values):
    actual, expected = values[condition['field']], condition['value']
    op = condition['op']
    if op == 'eq': return actual == expected
    if op == 'ne': return actual != expected
    if op == 'in': return actual in expected
    if op == 'not_in': return actual not in expected
    if op == 'gt': return actual > expected
    if op == 'gte': return actual >= expected
    if op == 'lt': return actual < expected
    if op == 'lte': return actual <= expected
    raise ConfigurationError('unsupported predicate')


def validate_definition(value):
    _keys(value, ('schema_version', 'workflow_id', 'version', 'description', 'resource_schema', 'resource_freshness_seconds', 'operations'))
    _require(type(value['schema_version']) is int and value['schema_version'] == 1, 'unsupported schema version')
    _require(_name(value['workflow_id']) and _name(value['version']), 'invalid workflow identifier or version')
    _require(type(value['description']) is str and 1 <= len(value['description']) <= 2048, 'invalid description')
    _schema(value['resource_schema'], object_root=True)
    freshness = value['resource_freshness_seconds']
    _require(type(freshness) is int and 1 <= freshness <= 31536000, 'invalid resource freshness')
    operations = value['operations']
    _require(type(operations) is dict and 1 <= len(operations) <= 32 and all(_name(k) for k in operations), 'invalid operations')
    for operation in operations.values():
        _keys(operation, ('description', 'adapter', 'parameters', 'allowed_roles', 'resource_checks', 'approval', 'budgets'))
        _require(type(operation['description']) is str and 1 <= len(operation['description']) <= 2048, 'invalid operation description')
        _require(_name(operation['adapter']), 'adapter must be a registered identifier')
        _require(_strings(operation['allowed_roles']), 'invalid allowed roles')
        _schema(operation['parameters'], object_root=True)
        _conditions(operation['resource_checks'], value['resource_schema'])
        approval = operation['approval']
        _keys(approval, ('reviewer_roles', 'ttl_seconds', 'when'))
        _require(_strings(approval['reviewer_roles']), 'invalid reviewer roles')
        _require(type(approval['ttl_seconds']) is int and 1 <= approval['ttl_seconds'] <= 86400, 'invalid approval expiration')
        _conditions(approval['when'], operation['parameters'])
        budgets = operation['budgets']
        _require(type(budgets) is list and len(budgets) <= 16, 'invalid budgets')
        seen = set()
        for budget in budgets:
            _keys(budget, ('parameter', 'limit', 'scope'))
            parameter = budget['parameter']
            _require(type(parameter) is str and parameter in operation['parameters']['required'], 'budget parameter must be required')
            field = operation['parameters']['properties'][parameter]
            _require(field['type'] == 'integer' and field['minimum'] > 0, 'budget parameter must be positive integer')
            _require(type(budget['limit']) is int and 1 <= budget['limit'] <= 2**53, 'invalid budget limit')
            _require(budget['scope'] in ('tenant', 'resource'), 'invalid budget scope')
            key = (parameter, budget['scope'])
            _require(key not in seen, 'duplicate budget')
            seen.add(key)
    return value


@dataclass(frozen=True)
class WorkflowDefinition:
    _json: str

    @classmethod
    def from_dict(cls, value):
        try:
            validate_definition(value)
            return cls(canonical(value))
        except (TypeError, KeyError, OverflowError) as exc:
            raise ConfigurationError('malformed workflow definition') from exc

    def to_dict(self):
        return json.loads(self._json)

    @property
    def workflow_id(self): return self.to_dict()['workflow_id']

    @property
    def version(self): return self.to_dict()['version']

    @property
    def digest(self): return digest(self.to_dict())


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, 'duplicate JSON field')
        value[key] = item
    return value


class WorkflowRegistry:
    def __init__(self, definitions):
        workflows = {}
        for item in definitions:
            definition = WorkflowDefinition.from_dict(item.to_dict() if isinstance(item, WorkflowDefinition) else item)
            _require(definition.workflow_id not in workflows, 'duplicate workflow identifier')
            workflows[definition.workflow_id] = definition
        _require(bool(workflows), 'empty workflow registry')
        self.workflows = MappingProxyType(workflows)

    @classmethod
    def from_paths(cls, paths):
        definitions = []
        for path in paths:
            with open(path, encoding='utf-8') as stream:
                definitions.append(json.load(stream, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ConfigurationError('nonfinite JSON number'))))
        return cls(definitions)

    def get(self, workflow_id):
        try:
            return self.workflows[workflow_id]
        except (KeyError, TypeError) as exc:
            raise ConfigurationError('unknown workflow') from exc
