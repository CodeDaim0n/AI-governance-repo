"""Generate the 12 assessment outputs from evidence, preserving unknowns."""
import csv,json
from pathlib import Path
r=Path(__file__).resolve().parents[1]
summary=json.loads((r/'results/summary.json').read_text())
risks=json.loads((r/'docs/risk-register.json').read_text())
steps=list(csv.DictReader((r/'docs/step-product-matrix.csv').open()))
sections={
'4.1':{'workflow':'Synthetic UK credit action workflow','completeness':'Partial','missing':['Named owners','real KYC/core adapters','deployment topology evidence','legal applicability approval','representative model validation','retention schedule']},
'4.2':{'readiness':'Restricted laboratory only','production_approval':False,'authority':'Unassigned accountable human release authority'},
'4.3':{'analysis':steps,'interpretation':'Product assignments are target design, not proof of integration'},
'4.4':{'risk_register':risks},
'4.5':{'autonomy':'Synthetic ledger writes only','per_action_pence':1000000,'human_review_above_pence':100000,'aggregate_lifetime_tenant_budget_pence':1500000,'unknown':['real delegation and target privilege evidence']},
'4.6':{'implemented':['schema validation','RS256 lab identity','OPA action and context policy','action-bound approvals','aggregate budget','idempotency','atomic local evidence','kill switch','HTTP outbox'],'required':['network bypass prevention','native source and risk connectors','durable workflow','external evidence anchoring']},
'4.7':{'mapping_file':'docs/framework-mapping.csv','assessment_status':'Evidence-limited alignment, not certification'},
'4.8':{'observed_test_results':summary,'required':['independent business validation','fairness','human factors','enterprise penetration testing','DR drill','distributed target reconciliation']},
'4.9':{'local':'denials queue incident events; admin stop blocks new writes','production':'SOC triage, bounded outbox, monitoring, escalation and manual service fallback required'},
'4.10':{'benefits':'Not measured','costs':'Not measured','autonomy_expansion':'Not justified by these tests'},
'4.11':{'priority_actions':[{'priority':'P0','action':x['title'],'owner':x['owner_role'],'status':x['treatment_status']} for x in risks if 'Not demonstrated' in x['assurance_status'] or 'unresolved' in x['assurance_status']]},
'4.12':{'assessment_version':'1.0','date':'2026-11-02','sources':'docs/references.json','policy':'credit-policy-1','limitations':'Self-authored local control tests; no independent audit or production observation'}
}
(r/'results/assessment.json').write_text(json.dumps(sections,indent=2))
print('12 evidence-backed assessment sections generated')
