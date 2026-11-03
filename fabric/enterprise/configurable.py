"""Optional native authorities for the configurable runtime.

Bindings are administrator-owned deployment input, separate from agent actions.
Native checks add restrictions to the runtime's mandatory controls. These adapters
do not establish deployment acceptance or turn a synthetic target into a real API.
"""
import json
import os
from pathlib import Path

import httpx

from fabric.runtime import ConfigurableFabric
from fabric.core import digest
from .postgres import Connection
from .clients import OpenFGA, OpenMetadata, MLflowRegistry, GLPI, DependencyFailure


class ConfigurablePostgresFabric(ConfigurableFabric):
    def connect(self):
        return Connection(self.path)


class NativeAuthorities:
    """Explicit per-workflow native requirements; no missing-binding fallback."""
    CAPABILITIES = {"opa", "relationships", "metadata", "model", "inventory"}
    FIELDS = {
        "required_capabilities", "opa_decision_url", "fga_user_type",
        "fga_object_type", "fga_relation", "metadata_entity_type",
        "metadata_entity_collection", "metadata_entity_fqn", "metadata_required_tag",
        "model_tenant", "model_name", "model_metric_requirements", "glpi_service_type", "glpi_service_id", "glpi_entity_id",
    }

    def __init__(self, registry, bindings_path=None):
        path = bindings_path or os.environ.get("FABRIC_NATIVE_BINDINGS")
        if not path:
            raise ValueError("FABRIC_NATIVE_BINDINGS is required for native authorities")
        from .configuration import parse_json
        document = parse_json(Path(path).read_text(encoding="utf-8"), "Native bindings")
        if (not isinstance(document, dict) or set(document) != {"schema_version", "workflows"}
                or document["schema_version"] != "1.0" or not isinstance(document["workflows"], dict)):
            raise ValueError("Invalid native binding document")
        self.bindings = document["workflows"]
        if set(self.bindings) != set(registry.workflows):
            raise ValueError("Native bindings must cover exactly the loaded workflows")
        for binding in self.bindings.values():
            if not isinstance(binding, dict) or set(binding) - self.FIELDS:
                raise ValueError("Unknown native binding field")
            caps = binding.get("required_capabilities")
            if (not isinstance(caps, list) or not all(isinstance(x, str) for x in caps)
                    or len(set(caps)) != len(caps) or set(caps) - self.CAPABILITIES
                    or not {"opa", "relationships"}.issubset(caps)):
                raise ValueError("Native bindings require OPA and relationship authority")
            for key, value in binding.items():
                if key not in {"required_capabilities", "model_metric_requirements"} and (not isinstance(value, str) or not value):
                    raise ValueError("Native binding values must be nonempty strings")
            if not binding.get("opa_decision_url", "").startswith(("https://", "http://")):
                raise ValueError("An administrator-owned OPA decision URL is required")
            for key in ("fga_user_type", "fga_object_type", "fga_relation"):
                if key not in binding:
                    raise ValueError("Explicit FGA types and relation are required")
            required_fields = {
                "metadata": {"metadata_entity_type", "metadata_entity_collection", "metadata_entity_fqn", "metadata_required_tag"},
                "inventory": {"glpi_service_type", "glpi_service_id", "glpi_entity_id"},
                "model": {"model_tenant", "model_name", "model_metric_requirements"},
            }
            for capability, fields in required_fields.items():
                if capability in caps and not fields.issubset(binding):
                    raise ValueError("Explicit per-workflow binding required for " + capability)
            if "model_metric_requirements" in binding:
                from .configuration import validate_metric_requirements
                validate_metric_requirements(binding["model_metric_requirements"])

    @staticmethod
    def resource_key(workflow_id, tenant, resource_id):
        # Canonical tuple encoding cannot collide when tenant/resource contain '/'.
        return digest([workflow_id, tenant, resource_id])

    @staticmethod
    def _metadata(binding):
        metadata = OpenMetadata()
        try:
            metadata.assert_classified(**{key.removeprefix("metadata_"): value
                for key, value in binding.items() if key.startswith("metadata_")})
        finally:
            metadata.close()

    def authorize_read(self, principal, resource, definition):
        binding = self.bindings[definition.workflow_id]
        fga = OpenFGA()
        try:
            # Compound IDs prevent reusing a relation from a different workflow.
            scoped = self.resource_key(definition.workflow_id, resource["tenant"], resource["id"])
            allowed = fga.check(principal["id"], scoped, user_type=binding["fga_user_type"],
                                object_type=binding["fga_object_type"], relation=binding["fga_relation"])
            if allowed and "metadata" in binding["required_capabilities"]:
                self._metadata(binding)
            return allowed
        finally:
            fga.close()

    def decide(self, ctx):
        workflow_id = ctx["action"]["workflow_id"]
        binding = self.bindings[workflow_id]
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            response = client.post(binding["opa_decision_url"], json={"input": ctx})
            response.raise_for_status()
            result = response.json().get("result")
        if (not isinstance(result, dict) or type(result.get("allow")) is not bool
                or result.get("config_digest") != ctx["config_digest"]):
            raise DependencyFailure("OPA decision missing deployed configuration binding")
        if not result["allow"]:
            return {"allow": False}
        fga = OpenFGA()
        try:
            scoped = self.resource_key(workflow_id, ctx["principal"]["tenant"], ctx["resource"]["id"])
            if not fga.check(ctx["principal"]["id"], scoped,
                             user_type=binding["fga_user_type"], object_type=binding["fga_object_type"],
                             relation=binding["fga_relation"]):
                return {"allow": False}
        finally:
            fga.close()
        caps = binding["required_capabilities"]
        if "metadata" in caps:
            self._metadata(binding)
        if "model" in caps:
            if ctx["principal"]["tenant"] != binding["model_tenant"]:
                return {"allow": False}
            MLflowRegistry().validate(model_name=binding["model_name"], metric_requirements=binding["model_metric_requirements"])
        if "inventory" in caps:
            inventory = GLPI()
            try:
                record = inventory.service(**{key.removeprefix("glpi_"): value
                    for key, value in binding.items() if key.startswith("glpi_")})
                if record.get("is_deleted") or not record.get("id"):
                    raise DependencyFailure("Service inventory invalid")
            finally:
                inventory.close()
        return {"allow": True}
