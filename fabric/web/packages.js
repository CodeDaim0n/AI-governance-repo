const MAX_BYTES = 262144;
const MAX_WORKFLOWS = 16;
const encoder = new TextEncoder();
const SECTION_TITLES = {
  "4.1": "Understanding and gaps", "4.2": "Decision advice", "4.3": "Analysis by operation",
  "4.4": "Risk records", "4.5": "Autonomy boundaries", "4.6": "Control designs",
  "4.7": "Requirements traceability", "4.8": "Validation design", "4.9": "Operational response",
  "4.10": "Value and restraint", "4.11": "Remediation priorities", "4.12": "Assessment history",
};

function node(tag, attributes = {}, children = []) {
  const result = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (key === "text") result.textContent = value;
    else if (key === "className") result.className = value;
    else if (key === "disabled") result.disabled = Boolean(value);
    else result.setAttribute(key, String(value));
  }
  for (const child of children) result.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return result;
}

const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
const copy = value => JSON.parse(JSON.stringify(value));
const pretty = value => JSON.stringify(value, null, 2);
const name = value => typeof value === "string" && value ? value.slice(0, 100) : "Untitled workflow";

// Parsing before POST must not erase duplicate keys or round oversized integers.
// JSON.parse establishes syntax; the bounded scan preserves those extra checks.
function parseJSON(text, { allowPackage = false } = {}) {
  if (encoder.encode(text).byteLength > MAX_BYTES) throw new Error("JSON must fit within 256 KiB.");
  const parsed = JSON.parse(text);
  const packageWrapper = allowPackage && object(parsed) && Array.isArray(parsed.workflow_definitions);
  let index = 0;
  const whitespace = () => { while (/\s/.test(text[index] || "") && index < text.length) index += 1; };
  function string() {
    const start = index++;
    while (index < text.length) {
      if (text[index] === "\\") index += 2;
      else if (text[index++] === '"') return JSON.parse(text.slice(start, index));
    }
    throw new Error("Incomplete JSON string.");
  }
  function value(depth, inDefinition) {
    if (depth > 64) throw new Error("JSON nesting is too deep for this editor.");
    whitespace();
    if (text[index] === "{") {
      index += 1;
      whitespace();
      const keys = new Set();
      if (text[index] === "}") { index += 1; return; }
      while (index < text.length) {
        whitespace();
        const key = string();
        if (keys.has(key)) throw new Error(`Duplicate JSON field: ${key.slice(0, 80)}.`);
        keys.add(key);
        whitespace();
        index += 1; // colon, already checked by JSON.parse
        value(depth + 1, inDefinition || (packageWrapper && depth === 0 && key === "workflow_definitions"));
        whitespace();
        if (text[index++] === "}") return;
      }
    } else if (text[index] === "[") {
      index += 1;
      whitespace();
      if (text[index] === "]") { index += 1; return; }
      while (index < text.length) {
        value(depth + 1, inDefinition);
        whitespace();
        if (text[index++] === "]") return;
      }
    } else if (text[index] === '"') string();
    else {
      const token = text.slice(index).match(/^(?:true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/)?.[0];
      if (!token) throw new Error("Invalid JSON value.");
      if (/^-?\d/.test(token)) {
        // The workflow contract supports integer numbers only. Reject their
        // floating-point spellings before JSON.stringify can erase the type.
        if (inDefinition && /[.eE]/.test(token)) {
          throw new Error("Workflow numbers must use integer notation, without decimals or exponents.");
        }
        const number = Number(token);
        if (!Number.isFinite(number) || (Number.isInteger(number) && !Number.isSafeInteger(number))) {
          throw new Error("Use finite numbers and integers within the browser's safe integer range.");
        }
      }
      index += token.length;
    }
  }
  value(0, !packageWrapper);
  return parsed;
}

function definition(text) {
  const value = parseJSON(text);
  if (!object(value)) throw new Error("Each workflow must be a JSON object.");
  return value;
}

export function initPackages({ api, download, announce, bootstrap } = {}) {
  const host = document.getElementById("view-packages");
  if (!host || typeof api !== "function" || typeof download !== "function") {
    throw new Error("Package editor needs its view, API and download helpers.");
  }
  let entries = [];
  let sequence = 0;
  let revision = 0;
  let pending = false;
  let loaded = false;
  let currentResult = null;
  const list = node("div", { className: "stack" });
  const selection = node("p", { className: "muted" });
  const status = node("p", { className: "notice", role: "status", "aria-live": "polite", "aria-atomic": "true" });
  const results = node("section", { className: "stack", "aria-label": "Generated review package" });
  results.hidden = true;
  const build = node("button", { type: "button", className: "button button-primary", text: "Create review package", disabled: true });
  const file = node("input", { id: "package-import-file", type: "file", accept: ".json,application/json", className: "input" });
  const exports = [
    ["Package JSON", "governance-package.json", result => pretty(result.package), "application/json"],
    ["Assessment Markdown", "governance-assessment.md", result => result.report, "text/markdown"],
    ["Disabled OPA manifest", "opa-data-disabled.json", result => pretty(result.package.opa_data), "application/json"],
  ].map(([label, filename, content, mime]) => {
    const button = node("button", { type: "button", className: "button button-secondary", text: label, disabled: true });
    button.addEventListener("click", () => {
      if (!currentResult) return;
      download(filename, content(currentResult), mime);
      if (typeof announce === "function") announce(`${label} download prepared.`);
    });
    return button;
  });

  function setStatus(message, error = false) {
    status.textContent = message;
    status.className = error ? "notice notice-warning" : "notice";
    status.setAttribute("role", error ? "alert" : "status");
  }

  function updateSelection() {
    const count = entries.filter(entry => entry.selected).length;
    selection.textContent = `${count} workflow${count === 1 ? "" : "s"} selected. Select between 1 and ${MAX_WORKFLOWS}.`;
    build.disabled = pending || count < 1 || count > MAX_WORKFLOWS;
    build.textContent = pending ? "Validating configuration…" : "Create review package";
    host.setAttribute("aria-busy", String(pending));
  }

  function invalidate(message = "Configuration changed. Create a new package to validate these settings.") {
    revision += 1;
    pending = false;
    currentResult = null;
    results.replaceChildren();
    results.hidden = true;
    exports.forEach(button => { button.disabled = true; });
    setStatus(message);
    updateSelection();
  }

  function makeField(label, control, hint) {
    const id = `package-field-${++sequence}`;
    control.id = id;
    const children = [node("label", { for: id, className: "field-label", text: label }), control];
    if (hint) {
      const help = node("small", { id: `${id}-help`, className: "muted", text: hint });
      control.setAttribute("aria-describedby", help.id);
      children.push(help);
    }
    return node("div", { className: "field" }, children);
  }

  function updateDefinition(entry, change) {
    if (!entry.value) return;
    change(entry.value);
    entry.text = pretty(entry.value);
    entry.editor.value = entry.text;
    entry.heading.textContent = name(entry.value.workflow_id);
    invalidate();
  }

  function textField(entry, label, value, change, hint, multiline = false) {
    const control = node(multiline ? "textarea" : "input", { className: multiline ? "textarea" : "input" });
    if (multiline) { control.rows = 3; control.maxLength = 2048; }
    else control.type = "text";
    control.value = typeof value === "string" ? value : "";
    control.addEventListener("input", () => updateDefinition(entry, draft => change(draft, control.value)));
    return makeField(label, control, hint);
  }

  function numberField(entry, label, value, change, hint, minimum) {
    const control = node("input", { type: "number", step: "1", className: "input" });
    if (minimum !== undefined) control.min = String(minimum);
    control.value = Number.isSafeInteger(value) ? String(value) : "";
    control.addEventListener("input", () => {
      const parsed = /^-?\d+$/.test(control.value) ? Number(control.value) : NaN;
      const valid = Number.isSafeInteger(parsed) && (minimum === undefined || parsed >= minimum);
      control.setAttribute("aria-invalid", String(!valid));
      updateDefinition(entry, draft => change(draft, valid ? parsed : null));
    });
    return makeField(label, control, hint);
  }

  function renderGuided(entry) {
    entry.guided.replaceChildren();
    const draft = entry.value;
    if (!draft) {
      entry.guided.append(node("p", { className: "notice notice-warning", text: "Correct the JSON below to use guided settings. Server validation is still required." }));
      return;
    }
    entry.guided.append(node("div", { className: "grid-two" }, [
      textField(entry, "Workflow version", draft.version, (value, text) => { value.version = text; }, "Use a version such as access-v2. Configuration changes receive a new digest."),
      numberField(entry, "Source freshness (seconds)", draft.resource_freshness_seconds, (value, number) => { value.resource_freshness_seconds = number; }, "Maximum age of authoritative resource facts.", 1),
    ]));
    entry.guided.append(textField(entry, "Workflow description", draft.description, (value, text) => { value.description = text; }, "Describe the supported operation and its intended scope.", true));
    if (!object(draft.operations)) return;
    for (const [operationName, operation] of Object.entries(draft.operations)) {
      if (!object(operation)) continue;
      const group = node("fieldset", { className: "panel" }, [node("legend", { text: `Operation: ${operationName}` })]);
      const body = node("div", { className: "panel-body stack" });
      group.append(body);
      body.append(node("p", { className: "muted", text: `Required adapter: ${typeof operation.adapter === "string" ? operation.adapter : "not specified"}` }));
      const roles = value => typeof value === "string" ? value.split(",").map(role => role.trim()).filter(Boolean) : [];
      body.append(textField(entry, "Roles allowed to request this operation", Array.isArray(operation.allowed_roles) ? operation.allowed_roles.join(", ") : "", (value, text) => {
        value.operations[operationName].allowed_roles = roles(text);
      }, "Comma-separated role names. The authenticated principal supplies its role."));
      if (object(operation.approval)) {
        const approval = operation.approval;
        body.append(node("div", { className: "grid-two" }, [
          textField(entry, "Independent reviewer roles", Array.isArray(approval.reviewer_roles) ? approval.reviewer_roles.join(", ") : "", (value, text) => {
            value.operations[operationName].approval.reviewer_roles = roles(text);
          }, "The requester cannot approve their own action."),
          numberField(entry, "Approval valid for (seconds)", approval.ttl_seconds, (value, number) => {
            value.operations[operationName].approval.ttl_seconds = number;
          }, "The server permits 1–86,400 seconds.", 1),
        ]));
        const conditions = Array.isArray(approval.when) ? approval.when : [];
        body.append(node("p", { className: "muted", text: conditions.length ? "A separate approval is required when any condition below matches." : "No additional approval condition is configured. Use advanced JSON to add one." }));
        conditions.forEach((condition, index) => {
          if (!object(condition)) return;
          const label = `Approval condition ${index + 1}: ${condition.field} ${condition.op}`;
          const setValue = (value, next) => { value.operations[operationName].approval.when[index].value = next; };
          const schema = operation.parameters?.properties?.[condition.field];
          if (Array.isArray(schema?.enum) && !Array.isArray(condition.value)) {
            const select = node("select", { className: "select" });
            const choices = schema.enum.filter(value => ["string", "number", "boolean"].includes(typeof value));
            choices.forEach((value, choice) => select.append(node("option", { value: String(choice), text: String(value) })));
            const current = choices.findIndex(value => value === condition.value);
            if (current < 0) select.prepend(node("option", { value: "", text: "Select a condition value" }));
            select.value = current < 0 ? "" : String(current);
            select.addEventListener("change", () => updateDefinition(entry, value => setValue(value, select.value === "" ? null : choices[Number(select.value)])));
            body.append(makeField(label, select));
          } else if (Number.isSafeInteger(condition.value)) {
            body.append(numberField(entry, label, condition.value, setValue, "Threshold uses the parameter's declared unit."));
          } else if (typeof condition.value === "string") {
            body.append(textField(entry, label, condition.value, setValue));
          } else {
            body.append(node("p", { className: "muted", text: `${label}: ${JSON.stringify(condition.value)}. Edit this condition in advanced JSON.` }));
          }
        });
      }
      if (Array.isArray(operation.budgets) && operation.budgets.length) {
        body.append(node("p", { className: "muted", text: "Budgets are lifetime totals shared across actors in the same workflow, operation and tenant." }));
        operation.budgets.forEach((budget, index) => {
          if (!object(budget)) return;
          body.append(numberField(entry, `${budget.scope} budget: ${budget.parameter}`, budget.limit, (value, number) => {
            value.operations[operationName].budgets[index].limit = number;
          }, "Use the parameter's declared unit. This is not a rolling time window.", 1));
        });
      }
      entry.guided.append(group);
    }
  }

  function card(entry) {
    const check = node("input", { type: "checkbox" });
    check.checked = entry.selected;
    entry.heading = node("strong", { text: name(entry.value?.workflow_id) });
    const label = node("label", { className: "row" }, [check, entry.heading]);
    const badge = node("span", { className: entry.imported ? "badge badge-amber" : "badge badge-teal", text: entry.imported ? "Imported definition" : "Synthetic template" });
    const header = node("div", { className: "panel-header row" }, [label, badge]);
    const content = node("div", { className: "panel-body stack" });
    content.hidden = !entry.selected;
    check.addEventListener("change", () => {
      entry.selected = check.checked;
      content.hidden = !entry.selected;
      invalidate("Selection changed. Create a new package for the selected workflows.");
    });
    entry.guided = node("div", { className: "stack" });
    const advanced = node("details", {}, [node("summary", { text: "Advanced: edit the complete workflow JSON" })]);
    entry.editor = node("textarea", { className: "textarea", rows: "15", spellcheck: "false" });
    entry.editor.value = entry.text;
    const jsonMessage = node("p", { className: "muted" });
    advanced.append(makeField("Workflow definition JSON", entry.editor, "Unknown fields and unsupported contracts are rejected by the server."), jsonMessage);
    entry.editor.addEventListener("input", () => {
      entry.text = entry.editor.value;
      try {
        entry.value = definition(entry.text);
        jsonMessage.textContent = "JSON can be read. Create a package for server validation.";
        entry.editor.setAttribute("aria-invalid", "false");
        entry.heading.textContent = name(entry.value.workflow_id);
      } catch (error) {
        entry.value = null;
        jsonMessage.textContent = error.message;
        entry.editor.setAttribute("aria-invalid", "true");
      }
      renderGuided(entry);
      invalidate();
    });
    const restore = node("button", { type: "button", className: "button button-ghost", text: entry.imported ? "Restore imported definition" : "Restore template" });
    restore.addEventListener("click", () => {
      entry.value = copy(entry.original);
      entry.text = pretty(entry.value);
      entry.editor.value = entry.text;
      entry.editor.setAttribute("aria-invalid", "false");
      jsonMessage.textContent = "Original settings restored. Server validation is required.";
      entry.heading.textContent = name(entry.value.workflow_id);
      renderGuided(entry);
      invalidate("Original settings restored. Create a new package to validate them.");
    });
    content.append(entry.guided, advanced, restore);
    renderGuided(entry);
    return node("section", { className: "panel" }, [header, content]);
  }

  function renderEntries() {
    list.replaceChildren(...entries.map(card));
    updateSelection();
  }

  function entryFor(value, imported = false) {
    const original = copy(value);
    return { original, value: copy(original), text: pretty(original), selected: true, imported };
  }

  file.addEventListener("change", async () => {
    const selectedFile = file.files?.[0];
    if (!selectedFile) return;
    invalidate("Reading workflow definitions…");
    const ticket = revision;
    try {
      if (selectedFile.size > MAX_BYTES) throw new Error("Choose a JSON file no larger than 256 KiB.");
      const parsed = parseJSON((await selectedFile.text()).replace(/^\uFEFF/, ""), { allowPackage: true });
      if (ticket !== revision) return;
      const definitions = Array.isArray(parsed) ? parsed : object(parsed) && Array.isArray(parsed.workflow_definitions) ? parsed.workflow_definitions : [parsed];
      if (!definitions.length || definitions.length > MAX_WORKFLOWS || !definitions.every(object)) {
        throw new Error("Import between 1 and 16 workflow objects, or an exported package containing workflow_definitions.");
      }
      const ids = definitions.map(value => value.workflow_id);
      if (ids.some(value => typeof value !== "string" || !value) || new Set(ids).size !== ids.length) {
        throw new Error("Each imported definition needs a different, nonempty workflow_id.");
      }
      entries.forEach(entry => { if (ids.includes(entry.value?.workflow_id)) entry.selected = false; });
      entries.push(...definitions.map(value => entryFor(value, true)));
      renderEntries();
      invalidate(`${definitions.length} definition${definitions.length === 1 ? "" : "s"} imported for review. Create a package to validate them. Existing copies with the same ID were deselected.`);
    } catch (error) {
      if (ticket === revision) setStatus(`Import failed: ${error.message}`, true);
    } finally { file.value = ""; }
  });

  function renderResult(result) {
    const packageData = result.package;
    const heading = node("h3", { text: "Configuration package ready for review", tabindex: "-1" });
    const rows = packageData.assessment.workflows.map(workflow => node("tr", {}, [
      node("td", { text: workflow.workflow_id }), node("td", { text: workflow.config_digest }),
    ]));
    const summary = node("div", { className: "panel" }, [
      node("div", { className: "panel-header" }, [heading, node("span", { className: "badge badge-amber", text: "Unapproved" })]),
      node("div", { className: "panel-body stack" }, [
        node("p", { className: "notice notice-warning", text: "Configuration validation is complete. Deployment approval, registered adapters and operational evidence remain required. The OPA manifest is disabled with no allowed tenants." }),
        node("p", { text: `Required adapters: ${packageData.required_adapter_ids.join(", ") || "None listed"}` }),
        node("div", { className: "table-wrap" }, [node("table", { className: "table" }, [
          node("thead", {}, [node("tr", {}, [node("th", { scope: "col", text: "Workflow" }), node("th", { scope: "col", text: "Configuration digest" })])]),
          node("tbody", {}, rows),
        ])]),
      ]),
    ]);
    results.replaceChildren(summary);
    for (const workflow of packageData.assessment.workflows) {
      const assessment = node("section", { className: "panel" }, [node("div", { className: "panel-header" }, [node("h4", { text: `${workflow.workflow_id}: twelve assessment areas` })])]);
      const body = node("div", { className: "panel-body stack" });
      for (const [id, label] of Object.entries(SECTION_TITLES)) {
        body.append(node("details", {}, [
          node("summary", { text: `${id} ${label}` }),
          node("pre", { className: "package-json", text: pretty(workflow.sections[id]) ?? "No section returned." }),
        ]));
      }
      assessment.append(body);
      results.append(assessment);
    }
    results.hidden = false;
    heading.focus();
  }

  build.addEventListener("click", async () => {
    if (pending) return;
    const chosen = entries.filter(entry => entry.selected);
    if (!chosen.length || chosen.length > MAX_WORKFLOWS) return;
    invalidate("Checking selected definitions…");
    const ticket = revision;
    try {
      const workflows = chosen.map(entry => {
        try { return definition(entry.text); }
        catch (error) { throw new Error(`${name(entry.value?.workflow_id)}: ${error.message}`); }
      });
      if (new Set(workflows.map(value => value.workflow_id)).size !== workflows.length) {
        throw new Error("Select only one definition for each workflow_id. Deselect the original if you imported a replacement.");
      }
      const payload = { workflows };
      if (encoder.encode(JSON.stringify(payload)).byteLength > MAX_BYTES) {
        throw new Error("The selected definitions together exceed the 256 KiB request limit. Select fewer or smaller definitions.");
      }
      pending = true;
      updateSelection();
      setStatus("Validating schemas and preparing the review package…");
      const result = await api("/api/package", { method: "POST", body: payload });
      if (ticket !== revision) return;
      const packageData = result?.package;
      const manifest = packageData?.opa_data?.fabric_workflows;
      if (!object(packageData) || packageData.deployment_status !== "unapproved" || packageData.secrets_included !== false ||
          !object(manifest) || !Object.values(manifest).every(value => object(value) && value.enabled === false && Array.isArray(value.allowed_tenants) && value.allowed_tenants.length === 0) ||
          !Array.isArray(packageData.assessment?.workflows) || !Array.isArray(packageData.required_adapter_ids) || typeof result.report !== "string") {
        throw new Error("The service returned an unexpected package. No download has been enabled.");
      }
      renderResult(result);
      currentResult = result;
      exports.forEach(button => { button.disabled = false; });
      setStatus("Package created from validated configuration. Review the assessment and unresolved implementation needs before deployment.");
    } catch (error) {
      const message = error.message === "invalid_workflow_configuration"
        ? "The workflow definition is invalid. Check its identifier, version, roles, approval conditions and required schema fields."
        : error.message || "The service could not complete the request.";
      if (ticket === revision) setStatus(`Package not created: ${String(message).slice(0, 1200)}`, true);
    } finally {
      if (ticket === revision) { pending = false; updateSelection(); }
    }
  });

  host.replaceChildren(
    node("div", { className: "panel" }, [
      node("div", { className: "panel-header" }, [node("p", { className: "eyebrow", text: "Configuration and packaging" }), node("h2", { text: "Prepare a reviewable workflow package" })]),
      node("div", { className: "panel-body stack" }, [
        node("p", { text: "Select the synthetic examples, adjust supported rules, or import your own workflow contract. Guided settings and advanced JSON stay in sync." }),
        node("p", { className: "notice notice-warning", text: "This creates a configuration assessment and a disabled deployment manifest. Accountable review, target integration and deployment approval remain separate steps. A prose design graph is not a runtime definition." }),
        node("div", { className: "field" }, [node("label", { for: "package-import-file", className: "field-label", text: "Import workflow JSON" }), file, node("small", { className: "muted", text: "Up to 256 KiB: one definition, an array, or an exported package's workflow_definitions." })]),
      ]),
    ]),
    list,
    node("div", { className: "panel" }, [node("div", { className: "panel-body stack" }, [selection, build, status, node("div", { className: "row" }, exports)])]),
    results,
  );

  function load(nextBootstrap) {
    if (loaded) return;
    const workflows = nextBootstrap?.workflows;
    if (!Array.isArray(workflows) || !workflows.every(object)) {
      setStatus("Workflow templates could not be loaded. Reload the studio or import a JSON definition.", true);
      return;
    }
    // A user can import a definition while bootstrap is still loading.
    // Preserve that work and avoid selecting its matching template as well.
    const existingIds = new Set(entries.map(entry => entry.value?.workflow_id));
    entries = workflows.map(value => {
      const entry = entryFor(value);
      if (existingIds.has(value.workflow_id)) entry.selected = false;
      return entry;
    }).concat(entries);
    loaded = true;
    renderEntries();
    invalidate("Choose the workflows and review their settings, then create a package for server validation.");
  }
  if (bootstrap) load(bootstrap);
  else updateSelection();
  return { load };
}
