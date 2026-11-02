import unittest
from pathlib import Path

from fabric.configuration import WorkflowRegistry
from fabric.design import assess, implementation_package


class WorkflowDesignTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.registry = WorkflowRegistry.from_paths([root / 'workflows/synthetic-credit.json', root / 'workflows/it-access.json'])

    def test_both_workflows_have_twelve_traceable_outputs_without_invented_assurance(self):
        result = assess(self.registry)
        self.assertEqual(len(result['workflows']), 2)
        for item in result['workflows']:
            self.assertEqual(set(item['sections']), {f'4.{i}' for i in range(1, 13)})
            self.assertEqual(item['config_digest'], self.registry.get(item['workflow_id']).digest)
            self.assertFalse(item['sections']['4.2']['production_approval'])
            self.assertIsNone(item['sections']['4.4']['ratings'])
            self.assertTrue(item['sections']['4.1']['missing'])
            self.assertEqual(item['sections']['4.12']['evidence'], [])

    def test_export_preserves_contracts_but_never_enables_deployment(self):
        package = implementation_package(self.registry)
        reloaded = WorkflowRegistry(package['workflow_definitions'])
        for key, definition in reloaded.workflows.items():
            self.assertEqual(definition.digest, self.registry.get(key).digest)
            self.assertIs(package['opa_data']['fabric_workflows'][key]['enabled'], False)
            self.assertEqual(package['opa_data']['fabric_workflows'][key]['allowed_tenants'], [])
        self.assertEqual(package['deployment_status'], 'unapproved')
        self.assertFalse(package['secrets_included'])
