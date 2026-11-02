"""Fail closed when consuming external deployment acceptance receipts."""


def validate_receipt(component, proof, deployment_id, source_commit):
    if not isinstance(proof, dict):
        raise ValueError("Malformed receipt")
    if proof.get("deployment_id") != deployment_id or proof.get("source_commit") != source_commit:
        raise ValueError("Receipt is for a different deployment or source")
    if proof.get("status") != "PASS":
        raise ValueError("Receipt does not establish successful acceptance")
    if component == 16:
        expected = {"before_policy": "target reachable", "after_policy": "target blocked", "gateway": "reachable"}
        if any(proof.get(k) != v for k, v in expected.items()):
            raise ValueError("Missing before/after isolation proof")
    elif component == 17:
        expected = ("image_scanned", "vulnerability_gate_passed", "signature_verified", "tamper_rejected")
        if any(proof.get(k) is not True for k in expected):
            raise ValueError("Missing release-gate operation proof")
    else:
        raise ValueError("Unsupported receipt component")
    return proof
