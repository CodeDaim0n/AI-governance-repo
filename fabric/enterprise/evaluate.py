"""Binary-classification evaluation; publish candidates, never approve releases.

With no data argument, uses the explicitly labelled eight-record synthetic
fixture. --data and --metric-requirements accept operator-supplied JSON files.
"""
import argparse
import hashlib
import json
from pathlib import Path

from .clients import MLflowRegistry
from .configuration import (ConfigurationError, enforce_metric_requirements,
                            metric_requirements, parse_json, validate_metric_requirements)

SUPPORTED_METRICS = frozenset(('fairness_difference', 'accuracy', 'selection_rate', 'accuracy_difference'))


def synthetic_fixture():
    return {
        'dataset': 'synthetic-eight-record-fixture',
        'y_true': [1, 0, 1, 0, 1, 0, 1, 0],
        'y_pred': [1, 0, 1, 0, 1, 0, 1, 0],
        'sensitive_features': ['a'] * 4 + ['b'] * 4,
    }


def validate_data(data):
    fields = {'dataset', 'y_true', 'y_pred', 'sensitive_features'}
    if not isinstance(data, dict) or set(data) != fields:
        raise ConfigurationError('Evaluation data requires dataset, y_true, y_pred and sensitive_features only')
    if (not isinstance(data['dataset'], str) or not data['dataset'].strip()
            or len(data['dataset']) > 200):
        raise ConfigurationError('Dataset must have a nonempty name of at most 200 characters')
    columns = [data[key] for key in ('y_true', 'y_pred', 'sensitive_features')]
    if (any(not isinstance(column, list) or not column for column in columns)
            or len({len(column) for column in columns}) != 1):
        raise ConfigurationError('Evaluation arrays must be nonempty and equal length')
    if any(type(value) is not int or value not in (0, 1) for column in columns[:2] for value in column):
        raise ConfigurationError('Binary labels and predictions must be integer 0 or 1')
    if any(not isinstance(value, str) or not value.strip() or len(value) > 200 for value in columns[2]):
        raise ConfigurationError('Sensitive features must contain nonempty bounded group names')
    if len(set(columns[2])) < 2:
        raise ConfigurationError('Group disparity evaluation requires at least two groups')
    return data


def compute_metrics(data):
    # Lazy imports keep configuration/CLI validation independent of the optional
    # native evaluation dependencies; no substitute metric implementation is used.
    from fairlearn.metrics import MetricFrame, selection_rate
    from sklearn.metrics import accuracy_score
    frame = MetricFrame(metrics={'approval_rate': selection_rate, 'accuracy': accuracy_score},
                        y_true=data['y_true'], y_pred=data['y_pred'],
                        sensitive_features=data['sensitive_features'])
    metrics = {
        'fairness_difference': float(frame.difference()['approval_rate']),
        'accuracy': float(frame.overall['accuracy']),
        'selection_rate': float(frame.overall['approval_rate']),
        'accuracy_difference': float(frame.difference()['accuracy']),
    }
    return metrics, frame.by_group.to_dict()


def evaluate(data=None, requirements=None):
    synthetic = data is None
    data = validate_data(synthetic_fixture() if synthetic else data)
    gates = metric_requirements() if requirements is None else validate_metric_requirements(requirements)
    if set(gates) - SUPPORTED_METRICS:
        raise ConfigurationError('This evaluator supports only: ' + ', '.join(sorted(SUPPORTED_METRICS)))
    metrics, group_metrics = compute_metrics(data)
    enforce_metric_requirements(metrics, gates)
    artifact = {
        'dataset': data['dataset'],
        'dataset_origin': 'synthetic_fixture' if synthetic else 'operator_supplied',
        'dataset_sha256': hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'record_count': len(data['y_true']),
        'group_metrics': group_metrics,
        'metric_requirements': gates,
        'limitations': ('This fixture tests metric plumbing, not fair lending validity or independent validation.'
                        if synthetic else 'Operator-supplied binary-classification data. These metrics alone do not establish deployment suitability or independent validation.'),
    }
    receipt = MLflowRegistry().publish_evaluation(metrics, artifact)
    return {'metrics': metrics, 'dataset': artifact['dataset'], 'dataset_origin': artifact['dataset_origin'],
            'metric_requirements': gates, 'receipt': receipt,
            'release': 'candidate only; an independent validator must promote'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    dataset = parser.add_mutually_exclusive_group()
    dataset.add_argument('--data', type=Path, help='JSON binary-classification dataset')
    dataset.add_argument('--synthetic', action='store_true', help='Use the explicit synthetic fixture (the default)')
    parser.add_argument('--metric-requirements', type=Path,
                        help='JSON metric-name -> min/max bounds; defaults to configured release requirements')
    args = parser.parse_args(argv)
    try:
        data = parse_json(args.data.read_text(encoding='utf-8'), 'Evaluation data') if args.data else None
        requirements = (parse_json(args.metric_requirements.read_text(encoding='utf-8'), 'Metric requirements')
                        if args.metric_requirements else None)
        result = evaluate(data, requirements)
    except (ConfigurationError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, allow_nan=False))
    return result


if __name__ == '__main__':
    main()
