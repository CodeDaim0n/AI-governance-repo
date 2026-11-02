package fabric
import rego.v1

reasons contains "identity_scope" if { input.principal.role != "agent" }
reasons contains "tenant_boundary" if { input.principal.tenant != input.case.tenant }
reasons contains "tool_not_allowed" if { input.action.tool != "credit.commit" }
reasons contains "kyc_not_clear" if { input.case.kyc != "clear" }
reasons contains "region_not_allowed" if { input.case.region != "UK" }
reasons contains "stale_context" if { input.now - input.case.updated > 60 }
reasons contains "future_context" if { input.case.updated > input.now + 5 }
reasons contains "workflow_not_approved" if { input.registry.approved != 1 }
reasons contains "validation_expired" if { input.registry.validated_until <= input.now }
reasons contains "kill_switch" if { input.stopped }
reasons contains "action_limit" if { input.action.amount_pence > 1000000 }
reasons contains "aggregate_budget" if { input.spent + input.action.amount_pence > 1500000 }
reasons contains "human_approval_required" if {
 input.action.amount_pence > 100000
 not input.approved
}
allow := count(reasons) == 0
decision := {"allow": allow, "reasons": sort(reasons), "version": "credit-policy-1"}
