package fabric_configurable_test
import rego.v1
import data.fabric_configurable

manifest := {"access": {"enabled": true, "config_digest": "approved-digest", "allowed_operations": ["grant"], "allowed_roles": ["agent"], "allowed_tenants": ["org"]}}
request := {"action": {"workflow_id": "access", "operation": "grant"}, "config_digest": "approved-digest", "principal": {"role": "agent", "tenant": "org", "active": 1}, "resource": {"tenant": "org"}}

test_approved_binding if { fabric_configurable.allow with input as request with data.fabric_workflows as manifest }
test_unknown_workflow if { not fabric_configurable.allow with input as object.union(request, {"action": {"workflow_id": "missing", "operation": "grant"}}) with data.fabric_workflows as manifest }
test_changed_config if { not fabric_configurable.allow with input as object.union(request, {"config_digest": "changed"}) with data.fabric_workflows as manifest }
test_other_tenant if { not fabric_configurable.allow with input as object.union(request, {"resource": {"tenant": "other"}}) with data.fabric_workflows as manifest }
test_unapproved_deployment if { not fabric_configurable.allow with input as request with data.fabric_workflows as {"access": object.union(manifest.access, {"enabled": false})} }
test_unlisted_operation if { not fabric_configurable.allow with input as object.union(request, {"action": {"workflow_id": "access", "operation": "delete"}}) with data.fabric_workflows as manifest }
