package fabric_test
import rego.v1
import data.fabric
base := {"principal":{"role":"agent","tenant":"a"},"case":{"tenant":"a","kyc":"clear","region":"UK","updated":100},"registry":{"approved":1,"validated_until":200},"stopped":false,"spent":0,"now":100,"action":{"tool":"credit.commit","amount_pence":10000},"approved":false}
test_allow if { fabric.decision.allow with input as base }
test_cross_tenant if { not fabric.decision.allow with input as object.union(base,{"case":object.union(base.case,{"tenant":"b"})}) }
test_approval if { not fabric.decision.allow with input as object.union(base,{"action":{"tool":"credit.commit","amount_pence":200000}}) }
test_kill if { not fabric.decision.allow with input as object.union(base,{"stopped":true}) }
test_budget if { not fabric.decision.allow with input as object.union(base,{"spent":1500000}) }
test_stale if { not fabric.decision.allow with input as object.union(base,{"now":161}) }
