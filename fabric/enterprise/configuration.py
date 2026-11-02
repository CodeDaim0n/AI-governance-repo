"""Validated operator configuration for native adapters; no agent input is read here.

Unset settings preserve the original laboratory profile. Present but invalid
settings are errors, including empty JSON objects and non-finite metric values.
"""
import json
import math
import os
import re
from collections.abc import Mapping


class ConfigurationError(ValueError):
    pass


DEFAULT_PRINCIPALS = ('agent-a', 'agent-b', 'reviewer-a', 'reviewer-b', 'admin-a')
DEFAULT_RISK_REASON = {
    'tenant_boundary': 'R01', 'human_approval_required': 'R02',
    'stale_context': 'R03', 'kyc_not_clear': 'R03',
    'aggregate_budget': 'R04', 'policy_unavailable': 'R09',
}
DEFAULT_EXECUTED_RISKS = ('R01', 'R02', 'R04')


def text_value(value, label):
    if (not isinstance(value, str) or not value or len(value) > 512
            or any(c.isspace() or ord(c) < 32 for c in value)):
        raise ConfigurationError(label + ' must be a nonempty bounded identifier')
    return value


def identifier(value, label):
    value = text_value(value, label)
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}', value):
        raise ConfigurationError(label + ' must be a single API type or relation name')
    return value


def setting(name, default=None, *, override=None, api_identifier=False):
    value = override if override is not None else os.environ.get(name, default)
    return (identifier if api_identifier else text_value)(value, name)


def parse_json(raw, label):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ConfigurationError(label + ' contains duplicate keys')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ConfigurationError(label + ' contains a non-finite value')

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(label + ' must contain valid JSON') from exc


def _json_setting(name, default):
    return parse_json(os.environ[name], name) if name in os.environ else default


def _identifiers(values, label):
    if not isinstance(values, (list, tuple)) or not values:
        raise ConfigurationError(label + ' must contain a nonempty identifier array')
    result = tuple(text_value(value, label) for value in values)
    if len(set(result)) != len(result):
        raise ConfigurationError(label + ' must not contain duplicates')
    return result


def allowed_principals():
    return frozenset(_identifiers(_json_setting('FABRIC_ALLOWED_PRINCIPALS_JSON',
                                               DEFAULT_PRINCIPALS),
                                  'FABRIC_ALLOWED_PRINCIPALS_JSON'))


def fga_binding(*, user_type=None, object_type=None, relation=None):
    return {
        'user_type': setting('FGA_USER_TYPE', 'user', override=user_type, api_identifier=True),
        'object_type': setting('FGA_OBJECT_TYPE', 'case', override=object_type, api_identifier=True),
        'relation': setting('FGA_RELATION', 'operator', override=relation, api_identifier=True),
    }


def metadata_binding(*, entity_type=None, entity_collection=None, entity_fqn=None,
                     required_tag=None):
    kind = setting('METADATA_ENTITY_TYPE', 'table', override=entity_type, api_identifier=True)
    # Custom types need an explicit collection: do not guess product URL plurals.
    collection = setting('METADATA_ENTITY_COLLECTION', 'tables' if kind == 'table' else None,
                         override=entity_collection, api_identifier=True)
    return {
        'entity_type': kind,
        'entity_collection': collection,
        'entity_fqn': setting('METADATA_ENTITY_FQN', os.environ.get('METADATA_TABLE_FQN'),
                              override=entity_fqn),
        'required_tag': setting('METADATA_REQUIRED_TAG', override=required_tag),
    }


def finite_number(value, label):
    if type(value) not in (int, float):
        raise ConfigurationError(label + ' must be a finite number')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ConfigurationError(label + ' must be a finite number')
    return value


def validate_metric_requirements(requirements):
    if not isinstance(requirements, Mapping) or not requirements:
        raise ConfigurationError('Metric requirements must be a nonempty object')
    checked = {}
    for metric, bounds in requirements.items():
        text_value(metric, 'Metric name')
        if (not isinstance(bounds, Mapping) or not bounds
                or set(bounds) - {'min', 'max'}):
            raise ConfigurationError('Each metric requires min and/or max bounds')
        limits = {key: finite_number(value, metric + '.' + key) for key, value in bounds.items()}
        if 'min' in limits and 'max' in limits and limits['min'] > limits['max']:
            raise ConfigurationError('Metric minimum exceeds maximum: ' + metric)
        checked[metric] = limits
    return checked


def metric_requirements():
    if 'MODEL_METRIC_REQUIREMENTS_JSON' in os.environ:
        return validate_metric_requirements(_json_setting('MODEL_METRIC_REQUIREMENTS_JSON', None))
    try:
        maximum = float(os.environ['FAIRNESS_MAX_DIFFERENCE'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError('FAIRNESS_MAX_DIFFERENCE is required for the legacy metric gate') from exc
    return validate_metric_requirements({'fairness_difference': {'max': maximum}})


def enforce_metric_requirements(metrics, requirements=None):
    """Shared release/validation gate. Missing, string, bool and NaN values deny."""
    gates = metric_requirements() if requirements is None else validate_metric_requirements(requirements)
    if not isinstance(metrics, Mapping):
        raise ConfigurationError('Evaluation metrics must be an object')
    for name, bounds in gates.items():
        if name not in metrics:
            raise ConfigurationError('Required evaluation metric missing: ' + name)
        value = finite_number(metrics[name], 'Evaluation metric ' + name)
        if ('min' in bounds and value < bounds['min']) or ('max' in bounds and value > bounds['max']):
            raise ConfigurationError('Evaluation threshold exceeded: ' + name)
    return gates


def dispatch_risk_mapping():
    mapping = _json_setting('FABRIC_DISPATCH_RISK_MAP_JSON', DEFAULT_RISK_REASON)
    if not isinstance(mapping, dict) or not mapping:
        raise ConfigurationError('FABRIC_DISPATCH_RISK_MAP_JSON must be a nonempty object')
    return {text_value(reason, 'Dispatch reason'): text_value(risk, 'Dispatch risk ID')
            for reason, risk in mapping.items()}


def executed_risk_ids():
    return _identifiers(_json_setting('FABRIC_EXECUTED_RISK_IDS_JSON', DEFAULT_EXECUTED_RISKS),
                        'FABRIC_EXECUTED_RISK_IDS_JSON')


def dispatch_storage_mode():
    mode = os.environ.get('FABRIC_DISPATCH_STORAGE', 'legacy')
    if mode not in ('legacy', 'configurable'):
        raise ConfigurationError('FABRIC_DISPATCH_STORAGE must be legacy or configurable')
    return mode


def workflow_risk_bindings():
    """Explicit workflow risk identifiers; absence never selects the lab mapping."""
    name = 'FABRIC_WORKFLOW_RISK_BINDINGS_JSON'
    if name not in os.environ:
        return {}
    bindings = _json_setting(name, None)
    if not isinstance(bindings, dict) or not bindings:
        raise ConfigurationError(name + ' must be a nonempty object')
    checked = {}
    for workflow_id, binding in bindings.items():
        text_value(workflow_id, 'Risk binding workflow ID')
        if not isinstance(binding, dict) or set(binding) != {'reason_to_risk', 'executed_risk_ids'}:
            raise ConfigurationError('Each workflow risk binding requires reason_to_risk and executed_risk_ids')
        reasons = binding['reason_to_risk']
        if not isinstance(reasons, dict) or not reasons:
            raise ConfigurationError('Workflow reason_to_risk must be a nonempty object')
        checked[workflow_id] = {
            'reason_to_risk': {text_value(reason, 'Workflow dispatch reason'): text_value(risk, 'Workflow risk ID')
                               for reason, risk in reasons.items()},
            'executed_risk_ids': _identifiers(binding['executed_risk_ids'], 'Workflow executed_risk_ids'),
        }
    return checked
