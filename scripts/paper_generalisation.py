"""Append the configurable-runtime and prose-design research sections.

Importing this module performs no I/O. The caller owns document construction,
pagination, rendering, SVG export and final visual inspection.
"""
import ast
import json
from pathlib import Path

from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.platypus import Spacer


def _lifecycle(box, arrow):
    drawing = Drawing(483, 280)
    nodes = [
        (0, 178, 'Workflow description', 'Untrusted source context, duties, constraints and unknowns.'),
        (171, 178, 'Review draft', 'Graph, quotations, proposed controls and open questions.'),
        (342, 178, 'Accountable review', 'Correct interpretation; determine authority and evidence needs.'),
        (342, 36, 'Config + adapters', 'Reviewed contract, explicit bindings and supported effects.'),
        (171, 36, 'Shared runtime', 'Independent authorization and transactional enforcement.'),
        (0, 36, 'Outcome evidence', 'Receipts, audit, outbox, tests and operational observations.'),
    ]
    for x, y, heading, body in nodes:
        box(drawing, x, y, 141, 86, heading, body)
    arrow(drawing, 141, 221, 171, 221)
    arrow(drawing, 312, 221, 342, 221)
    arrow(drawing, 412, 178, 412, 122)
    arrow(drawing, 342, 79, 312, 79)
    arrow(drawing, 171, 79, 141, 79)
    drawing.add(String(0, 13, 'A review draft cannot execute, provision or approve a deployment.',
                       fontName='FabricSans', fontSize=8.2, fillColor=colors.HexColor('#24364b')))
    return drawing


def _reuse(box, arrow):
    drawing = Drawing(483, 316)
    box(drawing, 0, 216, 224, 86, 'Workflow configuration',
        'Schemas, roles, source checks, approval conditions, freshness and lifetime budgets.')
    box(drawing, 259, 216, 224, 86, 'New effect adapter when required',
        'Operator-registered code with reviewed validation, transaction and receipt semantics.')
    box(drawing, 0, 98, 483, 86, 'Shared enforcement and evidence',
        'Tenant isolation; approved configuration; fresh sources; exact approval; budgets; stop state; '
        'idempotency; effect, audit and outbox transaction.', 'tested')
    box(drawing, 0, 8, 483, 60, 'Deployment-specific product bindings',
        'Identity, policy, metadata, evaluation, workflow and evidence services need explicit configuration and acceptance.')
    arrow(drawing, 112, 216, 112, 184)
    arrow(drawing, 371, 216, 371, 184)
    arrow(drawing, 241, 98, 241, 68)
    return drawing


def append_sections(p, sub, title, table, story, markdown, box, arrow, root):
    """Append ten sections using the existing paper helpers; return SVG drawings."""
    root = Path(root)

    def read_json(relative):
        return json.loads((root / relative).read_text(encoding='utf-8'))

    # Read the trusted, data-only catalog without executing its source module.
    catalog = {}
    for node in ast.parse((root / 'fabric/framework.py').read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('INPUTS', 'OUTPUTS'):
                    catalog[target.id] = ast.literal_eval(node.value)
    inputs, outputs = catalog['INPUTS'], catalog['OUTPUTS']
    summary = read_json('results/designer-validation/summary.json')
    agt = read_json('results/designer-validation/agt.json')
    postgres = read_json('results/designer-validation/native-postgres.log')
    configured = postgres['checks']['configurable_workflows']['checks']
    run_names = [
        '20261102-prose-intake', '20261102-prose-intake-fixed', '20261102-prefixed-designs',
        '20261102-reasoning-designs', '20261102-complete-graphs',
    ]
    runs = {name: read_json('results/workflow-designer/' + name + '/run-summary.json') for name in run_names}
    figures = {'generalisation-workflow-lifecycle': _lifecycle(box, arrow),
               'generalisation-reuse-boundaries': _reuse(box, arrow)}

    def page(heading):
        title('GENERALISATION / 0.5', heading)

    def figure(name, alternative):
        story.append(figures[name])
        story.append(Spacer(1, 12))
        markdown.append('![' + alternative + '](' + name + '.svg)')

    page('From a process description to governed execution')
    p('The generalisation separates three artifacts: a model-assisted governance draft, an engineering contract, '
      'and an observed execution record. They have different authors, validation requirements and authority. '
      'A useful draft can guide implementation without being executable or sufficient for release.')
    figure('generalisation-workflow-lifecycle', 'Description, review, configuration, runtime and evidence lifecycle')
    sub('Two connected contributions')
    p('First, a shared runtime executes multiple declared workflows through the same enforcement engine. '
      'Second, a structured Ollama designer interprets prose into a workflow graph, proposed controls and '
      'questions. The synthetic credit and access profiles demonstrate the former; vendor onboarding and '
      'museum lending are exploratory descriptions for the latter. Their domains are not silently substituted.')
    p('Accountable review remains a separate decision. A reviewer must correct source interpretation, determine '
      'actual permissions and obligations, and establish implementation and validation requirements. The '
      'designer has no business tools, target credentials, provisioning endpoint or approval operation.')
    p('This extension operationalises the Erdos workflow-input and assessment-output structure [1]. It does '
      'not claim that product selection is prescribed by that framework or that structured output constitutes '
      'framework conformity. The source already includes enforcement, evaluation and operational evidence.', True)

    page('What is reusable, configurable or newly implemented?')
    figure('generalisation-reuse-boundaries', 'Workflow configuration and reviewed adapters around shared enforcement')
    p('The shared engine supplies authorization, approval, freshness, idempotency, aggregate limits and evidence '
      'semantics. Workflow configuration supplies supported domain rules. An effect adapter supplies target '
      'behavior when a new action cannot be represented by an existing reviewed adapter. A new control '
      'mechanism outside the contract requires explicit implementation and tests.')
    sub('Product reuse is conditional')
    p('The eighteen component groups are a responsibility map. Identity realms, relationship tuples, metadata '
      'entities, model metrics, workflow queues and risk/evidence links remain deployment-specific. Existing '
      'clients and platform patterns can be reused, but new bindings still need commissioning and acceptance. '
      'The diagram does not mark the full native stack as operational.')
    p('The supplied legacy credit path remains a compatibility fixture for earlier experiments. New definitions '
      'use the configurable modules and cfg_ table family; old records are not silently migrated. Historical '
      'product observations do not approve new identities, source mappings, workflow configurations or targets.')
    p('Teal denotes the shared path exercised by selected local contract and storage checks. The new adapter '
      'and enterprise bindings remain engineering and deployment responsibilities, rather than model-generated authority.', True)

    page('Runtime contract and effect boundary')
    p('Every action contains exactly workflow_id, operation, resource_id, parameters and idempotency_key. '
      'Identity, tenant, resource facts, configuration and target endpoints are resolved by trusted services. '
      'Definitions use schema_version 1 and a digest of the complete workflow definition; changing a declared '
      'adapter binding or rule invalidates approval even when a human-readable version is unchanged. '
      'External native-service settings require separate change control.')
    table(['Contract element', 'Enforcement / scope'], [
        ('Operation schema', 'Bounded string, integer and Boolean parameters; unknown fields fail validation.'),
        ('Resource predicates', 'Declared comparisons over authoritative stored attributes; no eval or arbitrary imports.'),
        ('Approval', 'Separate current reviewer; exact action, actor/resource state, configuration and deployment approval version; expiry checked.'),
        ('Shared budgets', 'Positive integer lifetime counters across actors within workflow, operation and tenant; optional resource scope.'),
        ('Current authority', 'Active roles, tenant isolation, source freshness, approved configuration and stop state remain enforced.'),
        ('Policy composition', 'External policies add restrictions; they cannot convert an internal denial into permission.'),
        ('Adapter selection', 'Operator-registered identifier, never a model-supplied import path, URL or shell command.'),
    ], [118, 365])
    sub('Local atomicity is not a remote transaction guarantee')
    p('Adapters expose validate(operation) and apply(connection, context). The included credit-ledger and '
      'access-directory effects are synthetic local writes. Effect, usage, consumed approval, audit and outbox '
      'commit together. Scoped records retain receipts; audit/outbox fields are minimized. A hash chain detects '
      'modification but is not an independently immutable archive.')
    p('An HTTP call inside apply cannot be undone by a database rollback. Remote targets require target '
      'idempotency, conditional writes, durable delivery and reconciliation. Nested parameter objects, arbitrary '
      'expressions, rolling budgets and general graph execution are outside the current contract. Administration '
      'and explicit fixture provisioning remain separate from the agent API.')

    page('Seven framework inputs: candidate coverage, not completeness')
    p('The designer retains the original section identifiers and uses concise paraphrased labels [1]. '
      'The crosswalk below explains the implementation contribution and the evidence still required. '
      'A source mention changes coverage to requires_review; it does not establish completeness or applicability.')
    input_notes = {
        '3.1.1': 'Source facts and questions; establish intended outcomes, boundaries and baseline measures.',
        '3.1.2': 'Actors, steps, decisions and edges; confirm ordering, handoffs, exceptions and resumption.',
        '3.1.3': 'Proposed duties and tool links; verify real permissions, delegation and prohibited effects.',
        '3.1.4': 'Data entities and quotations; verify provenance, sensitivity, reliability and retention.',
        '3.1.5': 'Proposed human roles; name accountable people and assess affected parties and redress.',
        '3.1.6': 'Requirements as source claims; obtain versioned authority and qualified applicability decisions.',
        '3.1.7': 'Described safeguards; obtain tests, operating records, incidents and change evidence.',
    }
    table(['Source ID / paraphrased area', 'Candidate representation and remaining review'],
          [(item['id'] + ' ' + item['title'], input_notes[item['id']]) for item in inputs], [165, 318])
    sub('Grounding has a deliberately narrow meaning')
    p('Evidence contains exact contiguous quotations and offsets in the supplied description. Facts reference '
      'those quotations instead of introducing a separate verified-fact narrative. Every entity marked stated '
      'requires evidence references. Proposed and unknown entities, assumptions, and open questions remain '
      'explicit in the artifact.')
    p('These checks establish source presence, not truth or entailment. A genuine quotation may be attached '
      'to an unsupported inference. Likewise, a source-described control is not independent evidence that the '
      'control operates. Review must distinguish intended duties, actual permissions and demonstrated behavior.')
    p('The complete framework catalog is fabric/framework.py; docs/framework-extension-map.md records '
      'the source/engineering boundary and component relationships. No model-generated coverage status '
      'substitutes for an accountable assessment.', True)

    page('Twelve outputs: review artifacts with reserved authority')
    p('All twelve source output areas are retained. Their structured content is assembled from the validated '
      'draft and deterministic defaults. The labels below are paraphrases; the proposed product mappings and '
      'implementation status belong to this project. Every area remains a draft requiring review.')
    output_notes = {
        '4.1': 'Source coverage, assumptions, gaps and questions.',
        '4.2': 'Draft recommendation; production and deployment approval false.',
        '4.3': 'Step-to-risk and step-to-control references.',
        '4.4': 'Proposed scenarios and priorities; no residual-risk acceptance.',
        '4.5': 'Actors, tools and decisions; actual permissions unverified.',
        '4.6': 'Proposed controls and explicit implementation gaps.',
        '4.7': 'Candidate evidence links; applicability and mapping require review.',
        '4.8': 'Proposed tests; execution status not_run and no measured results.',
        '4.9': 'Monitoring/response suggestions; recovery not rehearsed.',
        '4.10': 'Benefits, costs and proportionality not established.',
        '4.11': 'Open remediation; human ownership and dates unassigned.',
        '4.12': 'Versions, source digests and reassessment triggers; no release decision.',
    }
    table(['Source ID / paraphrased output', 'Generated contribution and boundary'],
          [(item['id'] + ' ' + item['title'], output_notes[item['id']]) for item in outputs], [165, 318])
    p('Human-owner references must resolve to actors declared human. This validates a structural relationship, '
      'not that a named role exists, has been appointed, is independent, or possesses the required competence. '
      'Risk acceptance, legal applicability, final release and operational commissioning remain external decisions.')

    page('Prose design method, bounded repair and provenance')
    p('An operator selects an Ollama endpoint and model. The description is untrusted data, and inference '
      'requests supply the JSON schema for structured output [28-30]. The current prompt asks for all explicit '
      'authority restrictions and exception, handoff and post-decision paths within schema limits, using concise '
      'field text rather than fixed step/risk/control targets.')
    table(['Boundary', 'Current implementation'], [
        ('Input / transport', 'At most 12,000 characters; explicit HTTP(S) endpoint; no redirects or ambient proxy configuration.'),
        ('Response / content', '512 KiB response and 256 KiB design limits; strict duplicate-key, finite-number, Unicode and unknown-field checks.'),
        ('Mechanical validation', 'Category-specific IDs, typed references, exact quotation presence and human-only accountable owners.'),
        ('Correction', 'At most two total attempts; up to 64 safe diagnostic codes. Complete rejected JSON included only within 16 KiB.'),
        ('Reasoning option', 'Operator Boolean; 8,192 or 12,288 generation tokens with 16,384 context. Optional thinking field bounded to 128 KiB.'),
        ('No execution authority', 'Always draft_requires_review; execution disabled, runtime definitions empty and deployment approval false.'),
    ], [116, 367])
    sub('Observed provenance and time limits')
    p('Artifacts record source, prompt, schema, model-draft and artifact digests, reported model metadata, '
      'requested reasoning mode and attempt outcomes. Provider reasoning is excluded from design, report, '
      'repair and logs; optional diagnostic capture separately retains the full provider response. Hashes '
      'support traceability, not independent model-identity attestation.')
    p('The maximum configured budget is 600 seconds shared across attempts. Deadlines are checked before '
      'requests and between chunks; an in-flight HTTP operation may extend beyond that deadline. Hard '
      'wall-clock cancellation needs an external worker deadline. A malformed-Unicode guard was added '
      'after the final native run; regression covers it, while that run retains its original source hashes. '
      'The generation prompt and schema were not changed by this parser fix.')

    page('Empirical method: contracts, policies and real storage')
    p('The 2 November 2026 regression distinguishes simulated provider contracts from actual policy and '
      'storage execution. The local WSL run used Python ' + summary['python'] + ', OPA 1.0.1 and PostgreSQL '
      '16.2. Self-authored fixtures exercise selected invariants; they are neither a statistical safety estimate '
      'nor product certification.')
    table(['Evidence group', 'Result', 'Scope'], [
        ('Core regression', str(summary['tests_run']) + ' passed', 'Zero failures, errors or skips; includes 29 designer/CLI tests.'),
        ('Designer/CLI subset', '29 passed', 'Simulated inference: schema, repair, Unicode, transport and authority boundaries.'),
        ('Rego checks', str(summary['rego_tests']) + ' passed', 'Original and configurable policy checks executed with OPA.'),
        ('Enterprise contracts', '77 passed', 'Native API/configuration contracts; other service responses simulated.'),
        ('AGT wrapper', str(agt['passed']) + ' assertions', 'Installed govern wrapper; no full toolkit qualification.'),
        ('Real PostgreSQL', postgres['status'], 'Original controls, two configurable workflows and restart receipt replay.'),
        ('Compilation / docs', 'Passed', 'Source compilation and strict documentation build.'),
    ], [133, 78, 272])
    duplicate = configured['concurrent_duplicate_one_effect']
    budget = configured['shared_resource_budget_race']
    evidence = configured['audit_integrity_and_config_binding']
    p('Both configurable workflows denied execution before independent approval and reused receipts afterward. '
      'Approval substitution and changed configuration were denied. ' + str(duplicate['requests']) + ' concurrent '
      'duplicate requests produced ' + str(duplicate['additional_effects']) + ' additional effect. A shared '
      'resource budget across ' + str(budget['actors']) + ' actors admitted ' + str(budget['executed']) + ' of '
      + str(budget['requests']) + ' requests and denied ' + str(budget['denied']) + '. The '
      + str(evidence['executed_events']) + ' executed events matched ' + str(evidence['outbox_effects'])
      + ' outbox effects; restart replay introduced no new effects. Targets remained synthetic local tables.')
    p('The original CI failure arose from SQL_ASCII text returned as bytes. The runner now initializes UTF8 '
      'and checks fetch/rebind behavior. A later PostgreSQL decimal usage-sum result required validated '
      'normalization before serialization. Failed records and passing reruns are retained; neither change '
      'establishes complete eighteen-product live acceptance.', True)

    page('Five native design runs: retain failures and interruptions')
    p('Ollama served the recorded qwen3:8b model, identified in its catalogue as 8.2B parameters and Q4_K_M '
      'quantization. Two synthetic descriptions were reused during development. Prompts, compatibility '
      'handling and repair changed adaptively; the final two runs requested reasoning. These observations '
      'are not a benchmark or a controlled comparison of reasoning modes.')
    outcomes = [
        ('Initial intake', 'Provider metadata rejected; correction timed out'),
        ('Metadata compatibility', 'Duplicate IDs after both attempts'),
        ('Prefixed identifiers', 'Invalid references; repair removed a referenced actor'),
        ('Reasoning requested', 'Mechanical pass after correction'),
        ('Complete-path prompt', 'Mechanical pass on first attempt'),
    ]
    native_rows = []
    for index, name in enumerate(run_names):
        cases = {case['name']: case for case in runs[name]['cases']}
        vendor = cases['vendor-onboarding']
        vendor_text = outcomes[index][1] + '; ' + format(vendor['seconds'], '.2f') + ' s'
        if 'museum-loan' not in cases:
            museum_text = 'Interrupted; no completed result'
        else:
            museum = cases['museum-loan']
            reason = 'References failed after two attempts' if index == 3 else 'Quotations and references failed after two attempts'
            museum_text = reason + '; ' + format(museum['seconds'], '.2f') + ' s'
        native_rows.append((outcomes[index][0], vendor_text, museum_text))
    table(['Development stage', 'Vendor onboarding', 'Museum loan'], native_rows, [112, 196, 175])
    sub('What the accepted records establish')
    p('The first accepted vendor draft had five steps, three risks and three proposed controls; the final '
      'accepted draft had six steps, three risks and three controls. Acceptance here means only the configured '
      'mechanical checks passed. Both drafts required substantive revision after source comparison. No '
      'accepted museum artifact was produced, and interrupted museum cases are not counted as successes or failures.')
    p('Each run retains its implementation and input hashes, recorded outcomes and available provider '
      'responses. The five directories, in table order, are 20261102-prose-intake, '
      '20261102-prose-intake-fixed, 20261102-prefixed-designs, 20261102-reasoning-designs and '
      '20261102-complete-graphs under results/workflow-designer/. The two accepted vendor records are '
      'observations of changing development revisions, not independent repeated trials.', True)

    page('A mechanical pass still contains substantive defects')
    p('An independent assistant compared the accepted vendor drafts with their supplied description. The '
      'latest artifact preserves four source roles, separate-channel finance verification, unknown tool '
      'permissions and proposed human owners. It quotes forbidden AI effects and identifies prompt injection '
      'and unauthorized vendor addition. These improvements do not make its process design correct.')
    table(['Finding in latest vendor draft', 'Required substantive revision'], [
        ('Effect before final decision', 'Vendor addition precedes accept/reject. Establish acceptance prerequisites before the write; rejection must produce no effect.'),
        ('Incomplete exception path', 'Missing/conflicting records need an explicit paused state, review completion and resume condition; rejection needs an explanation.'),
        ('Weak risk-control fit', 'Bank verification does not enforce the AI write restriction. Specify independent boundaries for bank changes, vendor writes, orders and payments.'),
        ('Unsupported stated authority', 'Final acceptance authority and serial sequencing are inferred. Mark them proposed and obtain accountable confirmation.'),
        ('Underspecified validation', 'Define invalid inputs, positive controls, expected decisions, unchanged target state and correlated evidence; alteration alone is not invalidity.'),
        ('Missing information/context', 'Represent recommendation and verification evidence, record versions, rejection explanation, escalation and workflow-specific evaluation needs.'),
    ], [137, 346])
    sub('Implication for governance automation')
    p('Valid references can connect the wrong concepts, and genuine quotations can support neither the '
      'attached inference nor the claimed authority. The source comparison is diagnostic assistant review, '
      'not human approval, factual verification or operational assurance. The museum failures establish '
      'mechanical rejection only; invalid responses were not promoted into an accepted design.')
    p('These findings support a review-assisted prototype. They do not support unattended governance design '
      'for arbitrary processes, reliable identification of every restriction or risk, or automatic translation '
      'from a prose graph into an approved runtime contract. The absence of execution authority limits what '
      'a flawed draft can do, but does not remove the need to correct it before implementation.')

    page('Validity, reproduction and the next research questions')
    p('Two synthetic descriptions and one local model identity cannot establish domain generality. Adaptive '
      'prompt changes, repeated exposure to the examples, caching and hardware conditions prevent causal '
      'claims from latency differences. Assistant review lacks blinded human annotations. Simulated service '
      'responses and self-authored tests can share omissions with the implementation. Real PostgreSQL '
      'success does not qualify remote targets or the complete native stack.')
    sub('Reproduce the correct evidence layer')
    p('Run the ordinary core discovery and tests/enterprise suite for contract regression. The native '
      'PostgreSQL runner exercises storage concurrency and restart. For a new model observation, run '
      'scripts/run_workflow_designer.py with an explicit installed model, supplied descriptions and a new '
      'empty output directory; --thinking records the reasoning request, while --capture-model-responses '
      'retains sensitive source-derived content and provider reasoning. Keep failures and source hashes.')
    table(['Repository evidence / entry point', 'Purpose'], [
        ('results/designer-validation/', 'Final regression summary, policy/toolkit checks and PostgreSQL log.'),
        ('results/workflow-designer/*/run-summary.json', 'Five development runs; interrupted cases have separate records.'),
        ('20261102-complete-graphs/source-comparison.json', 'Latest vendor findings and absence of an accepted museum artifact; path relative to results/workflow-designer/.'),
        ('fabric/framework.py; docs/framework-extension-map.md', 'Seven inputs, twelve outputs and project component crosswalk.'),
        ('docs/configurable-workflows.md; docs/workflow-designer.md', 'Supported contracts, model operation, limits and reproduction commands.'),
    ], [239, 244])
    sub('Next research')
    p('Freeze model, prompt, schema and runtime revisions before held-out evaluation. Have independent '
      'domain reviewers annotate authority restrictions, exceptions and risk-control links; report agreement, '
      'correction effort and missed constraints alongside mechanical acceptance. Compare reasoning and '
      'repair strategies under controlled conditions. Extend remote-effect reconciliation under fault '
      'injection, then commission and test each required native component. Review drafts, enforced actions '
      'and operational approval must remain separate throughout that work.')
    return figures
