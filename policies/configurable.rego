package fabric_configurable
import rego.v1

# data.fabric_workflows is a separately reviewed deployment manifest. An absent
# workflow, disabled deployment or changed digest cannot grant authority.
default allow := false

configured := data.fabric_workflows[input.action.workflow_id]

allow if {
    configured.enabled == true
    input.config_digest == configured.config_digest
    input.action.operation in configured.allowed_operations
    input.principal.role in configured.allowed_roles
    input.principal.tenant in configured.allowed_tenants
    input.principal.tenant == input.resource.tenant
    input.principal.active == 1
}

default selected_digest := ""
selected_digest := data.fabric_workflows[input.action.workflow_id].config_digest
decision := {"allow": allow, "config_digest": selected_digest}
