import unittest
from fabric.enterprise.acceptance import validate_receipt


class ReceiptTests(unittest.TestCase):
    def proof(self):
        return {"status": "PASS", "deployment_id": "lab", "source_commit": "sha",
                "before_policy": "target reachable", "after_policy": "target blocked", "gateway": "reachable"}

    def test_successful_isolation_receipt(self):
        validate_receipt(16, self.proof(), "lab", "sha")

    def test_matching_provenance_does_not_make_failure_a_pass(self):
        for status in (None, "FAIL", "BLOCKED"):
            with self.assertRaises(ValueError):
                validate_receipt(16, {**self.proof(), "status": status}, "lab", "sha")

    def test_incomplete_or_wrong_deployment_rejected(self):
        for change in ({"deployment_id": "other"}, {"source_commit": "old"}, {"after_policy": "target reachable"}, {"gateway": "blocked"}):
            with self.assertRaises(ValueError):
                validate_receipt(16, {**self.proof(), **change}, "lab", "sha")

    def test_release_requires_all_actual_operations(self):
        checks = dict.fromkeys(("image_scanned", "vulnerability_gate_passed", "signature_verified", "tamper_rejected"), True)
        proof = {**self.proof(), **checks}
        validate_receipt(17, proof, "lab", "sha")
        for key in checks:
            for value in (False, "true", 1, None):
                with self.assertRaises(ValueError):
                    validate_receipt(17, {**proof, key: value}, "lab", "sha")
