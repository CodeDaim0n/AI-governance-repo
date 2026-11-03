import { initPackages } from './packages.js';

const $ = (id) => document.getElementById(id);
const state = { token: '', bootstrap: null, result: null, report: '', busy: false, job: null, importRevision: 0, componentChoices: new Map() };
const viewNames = { design: 'Design studio', packages: 'Workflow packages', components: 'Component library', lab: 'Execution lab' };
let toastTimer;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = String(text);
  if (className) element.className = className;
  return element;
}
function append(parent, ...children) { children.filter(Boolean).forEach((child) => parent.append(child)); return parent; }
function badge(text, kind = '') { return node('span', text, `badge ${kind ? `badge-${kind}` : ''}`); }
function button(text, action, kind = 'secondary') { const item = node('button', text, `button button-${kind}`); item.type = 'button'; item.addEventListener('click', action); return item; }
function notice(target, text) { target.textContent = text; target.hidden = !text; }
function announce(text) { clearTimeout(toastTimer); notice($('toast'), text); toastTimer = setTimeout(() => { $('toast').hidden = true; }, 6500); }
function download(filename, content, mime = 'application/json') {
  const data = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
  const url = URL.createObjectURL(new Blob([data], { type: `${mime};charset=utf-8` }));
  const link = node('a'); link.href = url; link.download = filename; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const safeName = (text) => String(text || 'workflow').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 65) || 'workflow';

const errorMessages = {
  model_catalog_unavailable: 'The model service is not reachable. Start Ollama, then check the connection again. Other workspace tools are available offline.',
  model_design_validation_failed: 'The model response did not pass the design checks after correction. Nothing was executed. Add clearer process detail or try another installed model.',
  model_request_failed: 'The model request failed. Check that Ollama is running and the model is installed, then try again.',
  model_timeout: 'The model did not finish within the configured budget. Try a smaller model or a shorter, clearer process description.',
  design_busy: 'A design is already running in this workspace. Wait for it to finish before starting another.',
  design_already_running: 'A design is already running in this workspace. Wait for it to finish before starting another.',
  job_not_found: 'This job is no longer available. The server may have restarted; generate a new draft.',
  invalid_session: 'This workspace session changed. Reload the page to reconnect.',
  session_required: 'This workspace session changed. Reload the page to reconnect.',
};
function friendly(error) {
  const code = typeof error === 'string' ? error : error?.message || 'Request failed';
  if (errorMessages[code]) return errorMessages[code];
  if (code.includes('timeout') || code.includes('deadline')) return errorMessages.model_timeout;
  if (code.includes('model') && code.includes('unavailable')) return errorMessages.model_request_failed;
  if (code === 'Failed to fetch' || code.includes('NetworkError')) return 'Cannot reach Fabric Studio. Check that the local server is still running, then reload this page.';
  return `The request could not be completed: ${code}. Check the inputs and try again.`;
}

async function api(path, options = {}) {
  const headers = { 'X-Fabric-Session': state.token, ...(options.headers || {}) };
  const request = { ...options, headers, credentials: 'same-origin', cache: 'no-store' };
  if (options.body !== undefined) { request.body = JSON.stringify(options.body); headers['Content-Type'] = 'application/json'; }
  const response = await fetch(path, request);
  let result;
  try { result = await response.json(); } catch { throw new Error('Invalid server response'); }
  if (!response.ok) throw new Error(typeof result.error === 'string' ? result.error : `Request failed (${response.status})`);
  return result;
}

function route() {
  const view = Object.hasOwn(viewNames, location.hash.slice(1)) ? location.hash.slice(1) : 'design';
  Object.keys(viewNames).forEach((name) => { $(`view-${name}`).hidden = name !== view; });
  document.querySelectorAll('[data-view]').forEach((link) => {
    if (link.dataset.view === view) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
  $('breadcrumb').replaceChildren(document.createTextNode('Workspace '), node('span', '/'), document.createTextNode(viewNames[view]));
  document.title = `${viewNames[view]} · Fabric Studio`;
}
window.addEventListener('hashchange', route);

function updateDescription() {
  state.importRevision += 1;
  $('char-count').textContent = `${$('description').value.length.toLocaleString()} / 12,000 characters`;
  if (!state.busy && state.result) {
    state.result = null; state.report = ''; $('design-result').hidden = true; $('design-result').replaceChildren();
  }
}

async function refreshModels() {
  const refresh = $('refresh-models'); refresh.disabled = true;
  $('model-status').classList.remove('connected'); $('model-status').textContent = 'Checking the configured model service…';
  try {
    const result = await api('/api/models');
    $('model-options').replaceChildren(...(result.models || []).map((item) => { const option = node('option'); option.value = item.name; return option; }));
    if (result.reachable) {
      const count = (result.models || []).length;
      $('model-status').textContent = count ? `${count} installed ${count === 1 ? 'model' : 'models'} · ${state.bootstrap.model.endpoint}` : 'Ollama is reachable, but no models are installed. Install a model in Ollama, then refresh.';
      $('model-status').classList.toggle('connected', count > 0);
      if (!$('model').value) $('model').value = result.default_model || result.models?.find((m) => m.name.startsWith('qwen3:8b'))?.name || result.models?.[0]?.name || '';
    } else $('model-status').textContent = `${friendly(result.error || 'model_catalog_unavailable')} Endpoint: ${state.bootstrap.model.endpoint}`;
  } catch (error) { $('model-status').textContent = friendly(error); }
  finally { refresh.disabled = false; }
}

function setBusy(busy) {
  state.importRevision += 1;
  state.busy = busy;
  for (const id of ['description', 'model', 'thinking', 'generate', 'description-file']) $(id).disabled = busy;
  document.querySelectorAll('[data-example]').forEach((item) => { item.disabled = busy; });
  $('generate').textContent = busy ? 'Design in progress…' : 'Generate governance draft →';
  $('design-progress').hidden = !busy;
}

async function startDesign(event) {
  event.preventDefault(); if (state.busy) return;
  notice($('design-error'), '');
  const description = $('description').value.trim(), model = $('model').value.trim();
  if (!description || !model) { notice($('design-error'), 'Add a workflow description and an installed model name.'); return; }
  setBusy(true); state.result = null; $('design-result').hidden = true;
  try {
    const job = await api('/api/design', { method: 'POST', body: { description, model, thinking: $('thinking').checked } });
    state.job = job.id;
    await pollDesign(job.id);
  } catch (error) { notice($('design-error'), friendly(error)); }
  finally { setBusy(false); }
}

async function pollDesign(id) {
  let failures = 0;
  for (;;) {
    let job;
    try { job = await api(`/api/jobs/${encodeURIComponent(id)}`); failures = 0; }
    catch (error) {
      failures += 1;
      if (failures >= 3) throw error;
      $('progress-detail').textContent = 'Connection interrupted. Trying to recover the job status…';
      await new Promise((resolve) => setTimeout(resolve, 2000)); continue;
    }
    const seconds = Math.round(job.elapsed_seconds || 0);
    $('progress-title').textContent = job.status === 'queued' ? 'Your design is queued' : 'Generating and checking your governance draft';
    $('progress-detail').textContent = `${Math.floor(seconds / 60)}m ${seconds % 60}s elapsed · The model may take several minutes. Keep this page open.`;
    if (job.status === 'succeeded') {
      state.result = job.result; state.report = job.report || ''; renderDesign(job.result);
      announce('Governance draft generated. Review the interpretation, risks and proposed controls.'); return;
    }
    if (job.status === 'failed') throw new Error(job.error || 'Design failed');
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
}

function stat(value, label) { return append(node('div', null, 'stat'), node('strong', value), node('span', label)); }
function details(title, content) { return append(node('details'), node('summary', title), typeof content === 'string' ? node('p', content) : content); }
function jsonDetails(title, data) { return details(title, node('pre', JSON.stringify(data, null, 2))); }
function names(ids, items) { const byId = new Map(items.map((item) => [item.id, item.label || item.name || item.title])); return (ids || []).map((id) => byId.get(id) || id).join(', ') || 'Unassigned'; }

function renderDesign(design) {
  const root = $('design-result'); root.replaceChildren(); root.hidden = false;
  const heading = node('div', null, 'result-heading');
  append(heading, append(node('div'), badge('Draft · human review required', 'amber'), node('h2', design.workflow.title), node('p', design.workflow.summary)));
  append(heading, append(node('div', null, 'row'), button('Download JSON ↓', () => download(`${safeName(design.workflow.title)}-design.json`, design)), button('Download report ↓', () => download(`${safeName(design.workflow.title)}-report.md`, state.report, 'text/markdown'))));
  const stats = append(node('div', null, 'stats-row'), stat(design.graph.steps.length, 'Workflow steps'), stat(design.risks.length, 'Proposed risks'), stat(design.controls.length, 'Proposed controls'), stat(design.questions.length, 'Review questions'));
  const tabs = node('div', null, 'result-tabs'); tabs.setAttribute('aria-label', 'Design sections');
  const content = node('div', null, 'result-panel');
  const screens = [
    ['Workflow map', () => renderGraph(design)],
    ['Risks & controls', () => renderRisks(design)],
    ['Review & gaps', () => renderReview(design)],
    ['12 assessment areas', () => renderFramework(design)],
    ['Source & provenance', () => renderEvidence(design)],
  ];
  for (const [index, [label, render]] of screens.entries()) {
    const item = button(label, () => {
      [...tabs.children].forEach((tab) => tab.setAttribute('aria-pressed', String(tab === item)));
      content.replaceChildren(render());
    }, 'ghost');
    item.setAttribute('aria-pressed', String(index === 0)); tabs.append(item);
  }
  content.append(renderGraph(design));
  append(root, heading, node('div', 'Structure, references and quote presence were checked. The process interpretation and control effectiveness still require review. This draft cannot execute or deploy a workflow.', 'notice'), stats, tabs, content);
}

function renderGraph(design) {
  const fragment = node('div'); const graph = design.graph;
  append(fragment, node('h3', 'Interpreted workflow'), node('p', 'Review each step and its explicit connections below. The display order is not an approved execution sequence.', 'muted'));
  const grid = node('div', null, 'step-grid');
  for (const step of graph.steps) {
    const card = node('article', null, 'step-card');
    append(card, append(node('div', null, 'row'), node('span', step.id, 'card-id'), badge(step.source_state === 'stated' ? 'Source-described' : step.source_state, step.source_state === 'stated' ? 'teal' : 'amber')),
      node('h3', step.label), node('p', step.description), node('div', 'ACTORS', 'subtle-label'), node('p', names(step.actor_ids, graph.actors)));
    grid.append(card);
  }
  fragment.append(node('div', null, 'section-subhead'), grid, node('h3', 'Connections & conditions', 'section-subhead'));
  const connections = node('div', null, 'connections');
  for (const edge of graph.edges) append(connections, append(node('div', null, 'connection'), node('strong', names([edge.from_step_id], graph.steps)), node('span', '→'), node('strong', names([edge.to_step_id], graph.steps)), badge(edge.source_state), node('small', edge.condition)));
  if (!graph.edges.length) connections.append(node('p', 'No connections were supplied in this draft. Confirm the sequence and exception paths.', 'muted'));
  fragment.append(connections);
  if (graph.decisions.length) {
    fragment.append(node('h3', 'Decision points', 'section-subhead'));
    for (const decision of graph.decisions) fragment.append(details(decision.question, `${decision.criteria.join(' · ')}. Proposed authority: ${names(decision.authority_actor_ids, graph.actors)}.`));
  }
  return fragment;
}

function renderRisks(design) {
  const root = node('div'); append(root, node('h3', 'Proposed risks and safeguards'), node('p', 'Priorities are model proposals. Owners must assess risks and confirm whether each control addresses its linked scenario.', 'muted'));
  for (const risk of design.risks) {
    const card = node('article', null, 'risk-card');
    append(card, append(node('div', null, 'row'), node('span', risk.id, 'card-id'), badge(`Proposed priority: ${risk.proposed_priority.replaceAll('_', ' ')}`, 'amber')), node('h3', risk.title), node('p', risk.scenario), node('div', 'IMPACT', 'subtle-label'), node('p', risk.impact), node('div', 'UNCERTAINTY', 'subtle-label'), node('p', risk.uncertainty));
    for (const control of design.controls.filter((item) => item.risk_ids.includes(risk.id))) {
      const c = node('div', null, 'control-card');
      append(c, badge('Proposed control', 'teal'), node('h3', control.recommendation), node('p', `Enforcement point: ${control.enforcement_point}`), node('p', `Proposed owner: ${names(control.owner_actor_ids, design.graph.actors)}`), node('p', `Validation to perform: ${control.validation}`), node('p', `Candidate components: ${names(control.component_ids, design.components)}`)); card.append(c);
    }
    root.append(node('div', null, 'section-subhead'), card);
  }
  return root;
}

function renderReview(design) {
  const root = node('div'); root.append(node('h3', 'Questions for the process owner'));
  for (const question of design.questions) root.append(append(node('div', null, 'review-item'), badge(question.blocking ? 'Blocking' : 'Review', question.blocking ? 'amber' : ''), node('div', question.question)));
  root.append(node('h3', 'Gaps and implementation work', 'section-subhead'));
  for (const gap of [...design.gaps, ...design.implementation_gaps]) root.append(append(node('div', null, 'review-item'), node('span', '◇'), node('div', gap.description)));
  root.append(node('h3', 'Assumptions to challenge', 'section-subhead'));
  if (!design.assumptions.length) root.append(node('p', 'No explicit assumptions were returned. Review for unmarked assumptions as well.', 'muted'));
  for (const item of design.assumptions) root.append(details(item.statement, item.rationale));
  root.append(node('div', 'After review, express supported controls in a workflow definition and implement any missing adapters. The Workflow packages screen validates those definitions separately.', 'notice'));
  return root;
}

function renderFramework(design) {
  const root = node('div', null, 'details-list');
  for (const output of Object.values(design.framework_outputs)) {
    const body = node('div'); append(body, node('p', output.description), badge('Draft · requires review', 'amber'), node('pre', JSON.stringify(output.content, null, 2)));
    root.append(details(`${output.id} · ${output.title}`, body));
  }
  return root;
}

function renderEvidence(design) {
  const root = node('div'); append(root, node('h3', 'Quoted source material'), node('p', 'These quotations occur in the supplied description. Presence does not verify truth, authority or the model’s interpretation.', 'muted'));
  for (const item of design.evidence) root.append(append(node('div'), node('div', item.id, 'subtle-label'), node('blockquote', item.quote, 'quote')));
  append(root, node('h3', 'Trace this draft', 'section-subhead'), jsonDetails('Generation and validation record', design.provenance), details('Original process description', node('pre', design.source.text)), jsonDetails('Seven input areas', design.framework_inputs));
  return root;
}

function renderComponents() {
  const query = $('component-search').value.trim().toLowerCase();
  const components = state.bootstrap.components.filter((item) => `${item.name} ${item.role} ${item.workflow_specific}`.toLowerCase().includes(query));
  const grid = $('component-grid'); grid.replaceChildren(); $('component-count').textContent = `${components.length} of 18 groups`;
  for (const component of components) {
    const card = node('article', null, 'panel component-card'), body = node('div', null, 'panel-body');
    append(body, node('span', component.id, 'component-number'), node('h2', component.name), node('p', component.role), details('What needs configuring', component.workflow_specific), details('Implementation & evidence scope', component.implementation_status));
    const field = node('div', null, 'field'), input = node('input'); input.id = `product-${component.id}`; input.className = 'input'; input.maxLength = 160; input.value = state.componentChoices.get(component.id) ?? component.name;
    const label = node('label', 'Product in your plan', 'field-label'); label.htmlFor = input.id;
    const status = node('p', '', 'component-status');
    function choiceChanged() {
      const value = input.value.trim(); state.componentChoices.set(component.id, value);
      status.textContent = value && value !== component.name ? 'Alternative product · adapter and acceptance testing required' : 'Reference product · deployment configuration and testing required';
    }
    input.addEventListener('input', choiceChanged); choiceChanged(); append(field, label, input, status); body.append(field); card.append(body); grid.append(card);
  }
  if (!components.length) grid.append(node('div', 'No matching components. Try a capability such as identity, policy or monitoring.', 'empty-state'));
}

function exportComponents() {
  const plan = {
    schema_version: 1, kind: 'governance_component_selection_plan', generated_at: new Date().toISOString(), status: 'review_required', deployment_approved: false, connections_tested: false,
    components: state.bootstrap.components.map((item) => ({ component_id: item.id, role: item.role, reference_product: item.name, selected_product: state.componentChoices.get(item.id) || null, status: 'integration_and_acceptance_required', workflow_configuration: item.workflow_specific })),
  };
  download('fabric-component-plan.json', plan); announce('Selection plan prepared for download. It contains no credentials or live connections.');
}

let demoResult = null;
async function runDemo() {
  const ids = [...document.querySelectorAll('input[name="lab-workflow"]:checked')].map((input) => input.value);
  if (!ids.length) { notice($('lab-error'), 'Select at least one workflow to run.'); return; }
  notice($('lab-error'), ''); $('lab-results').hidden = true; demoResult = null;
  $('run-demo').disabled = true; $('run-demo').textContent = 'Running isolated demo…';
  document.querySelectorAll('input[name="lab-workflow"]').forEach((input) => { input.disabled = true; });
  try {
    const result = await api('/api/demo', { method: 'POST', body: { workflow_ids: ids } }); demoResult = result;
    const root = $('lab-results'); root.replaceChildren(); root.hidden = false;
    append(root, append(node('div', null, 'result-heading'), append(node('div'), badge('Run completed', 'teal'), node('h2', 'Control checks, with recorded outcomes'), node('p', result.scope)), button('Download evidence ↓', () => download('fabric-demo-evidence.json', result))));
    append(root, append(node('div', null, 'stats-row'), stat(result.workflows.length, 'Workflows exercised'), stat(result.effects, 'Synthetic effects'), stat(result.audit_chain_valid ? 'Valid' : 'Invalid', 'Local audit chain'), stat('0', 'External systems changed')));
    for (const flow of result.workflows) {
      const journey = append(node('div', null, 'lab-journey'), node('h3', flow.workflow_id === 'synthetic-credit' ? 'Credit commitment' : 'IT access grant'));
      const steps = node('div', null, 'lab-steps');
      append(steps,
        append(node('div'), badge('01 · Before approval', 'amber'), node('h4', flow.before_approval.status), node('p', 'The effect is blocked until an independent reviewer approves the exact action.')),
        append(node('div'), badge('02 · After demo approval', 'teal'), node('h4', flow.after_approval.status), node('p', 'The runtime rechecks the configured controls and records a synthetic effect.')),
        append(node('div'), badge('03 · Matching retry', 'teal'), node('h4', flow.retry_returns_same_receipt ? 'Same receipt returned' : 'Receipt mismatch'), node('p', 'The same request does not create another effect.')));
      append(journey, steps, jsonDetails('Inspect the recorded result', flow)); root.append(journey);
    }
    root.append(node('div', 'These are selected checks against local synthetic targets. They do not establish that your configuration, replacement products or production deployment are ready.', 'notice'));
    announce('Isolated demo complete. Review the outcomes and download the evidence.');
  } catch (error) { notice($('lab-error'), friendly(error)); }
  finally { $('run-demo').disabled = false; $('run-demo').textContent = 'Run isolated demo ▷'; document.querySelectorAll('input[name="lab-workflow"]').forEach((input) => { input.disabled = false; }); }
}

async function boot() {
  route();
  $('design-form').addEventListener('submit', startDesign);
  $('description').addEventListener('input', updateDescription);
  $('model').addEventListener('input', updateDescription); $('thinking').addEventListener('change', updateDescription);
  $('refresh-models').addEventListener('click', refreshModels);
  $('description-file').addEventListener('change', async (event) => {
    const file = event.target.files?.[0]; if (!file) return;
    const importRevision = ++state.importRevision;
    try {
      if (file.size > 200000) throw new Error('Text files must be no larger than 200 KB');
      const text = await file.text(); if (text.length > 12000) throw new Error('Use at most 12,000 characters');
      if (state.busy || importRevision !== state.importRevision) { announce('The pending file import was skipped because the workflow changed. Import it again when ready.'); return; }
      $('description').value = text; updateDescription(); announce('Process description imported. Check it before generating a draft.');
    } catch (error) { notice($('design-error'), error.message); }
    finally { event.target.value = ''; }
  });
  $('component-search').addEventListener('input', () => { if (state.bootstrap) renderComponents(); });
  $('export-components').addEventListener('click', exportComponents);
  $('run-demo').addEventListener('click', runDemo);
  document.querySelectorAll('input[name="lab-workflow"]').forEach((input) => input.addEventListener('change', () => { demoResult = null; $('lab-results').hidden = true; }));
  try {
    state.bootstrap = await api('/api/bootstrap'); state.token = state.bootstrap.session_token;
    $('model').value = state.bootstrap.model.default_model || '';
    document.querySelectorAll('[data-example]').forEach((button) => button.addEventListener('click', () => {
      const example = state.bootstrap.examples.find((item) => item.id === button.dataset.example);
      if (example) { $('description').value = example.description; updateDescription(); notice($('design-error'), ''); $('description').focus(); }
    }));
    initPackages({ api, download, announce, bootstrap: state.bootstrap });
    state.bootstrap.components.forEach((item) => state.componentChoices.set(item.id, item.name)); renderComponents();
    await refreshModels();
  } catch (error) {
    notice($('connection-error'), friendly(error)); $('generate').disabled = true; $('run-demo').disabled = true; $('export-components').disabled = true;
  }
}

boot();
