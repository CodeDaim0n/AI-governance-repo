# Local governance Studio

Studio provides a browser interface for drafting a governance design, preparing a runtime package, exploring the eighteen component roles and running the two synthetic workflow demonstrations. It brings these existing capabilities into one local workspace. A generated design remains a proposal for review; it does not approve or deploy a workflow.

## Start Studio

Use Python 3.11 or newer from the repository checkout. Install the package, then start the local server:

```bash
python -m pip install -e .
python -m fabric.studio
```

The installed entry point is `fabric-studio`. Open `http://127.0.0.1:8765` in your browser; the server prints its address. Add `--open` to open the default browser automatically. Use `--port` to select a different local port. Stop the server with Ctrl+C.

On Windows, you can double-click `Start-Studio.cmd` in the repository instead. It requires Python 3.11 or newer on PATH, creates `.venv-studio`, installs the project and opens the browser. First-time setup needs internet access to install dependencies. Keep the terminal open while using Studio. After the initial setup, it reuses the environment; the editable installation picks up source changes. To install new dependencies after updating the repository, run `.venv-studio\Scripts\python.exe -m pip install -e .` from that directory.

Workflow packages, the component library and the execution lab work without a model service. For AI design, start Ollama separately and install a model that supports its structured-output API. Select that model when starting Studio:

```bash
python -m fabric.studio --ollama-url http://127.0.0.1:11434 --model qwen3:8b
```

The example model name is a configuration example, not a reliability recommendation. The operator fixes the endpoint and can supply a default model at server startup; the browser can select a model at that endpoint. Submitted descriptions are sent to that endpoint. A nonlocal endpoint therefore sends the description outside this machine; its retention and access rules also apply.

## Use the four screens

| Screen | What to do | What the result means |
| --- | --- | --- |
| Design studio | Describe a process, including people, data, decisions, exceptions and existing controls; request a draft. | A model interpretation with workflow structure, proposed risks and controls, source references and unresolved questions. Download JSON or Markdown for review. |
| Workflow packages | Load an example or supply a runtime definition, edit supported settings, and validate the package. | A structured assessment and implementation package. The generated OPA manifest is disabled and has no allowed tenants. Downloads do not grant deployment approval. |
| Component library | Search the eighteen component groups and inspect their roles and implementation boundaries. | A capability map. Listed tools are implementation choices; their presence here does not prove a service is connected or a control works. |
| Execution lab | Explicitly run the bundled synthetic credit and IT-access examples. | A fresh, isolated demonstration of denial before separate approval, execution after approval, repeat receipt handling and audit verification. The examples change only disposable local synthetic targets. |

### Review a design before engineering it

Generation can take several minutes. Keep the tab open while it runs. Studio permits one active design job, with the existing designer's bounded generation and correction attempts. Failed validation produces an error rather than an accepted design. Its time budget is checked during processing, but an in-flight network operation can extend beyond that budget; it is not hard cancellation.

Read the draft against the original description. Check the order of actions, exception and recovery paths, who actually has authority, whether each proposed control addresses its risk, and what evidence is missing. Exact quotation and reference checks establish selected mechanical properties; they cannot prove that an interpretation follows from its source or that the source is true. The [recorded native observations](validation.md#native-designer-observations-2026-11-02) include a structurally accepted draft with substantive defects.

The bridge from an AI draft to runtime configuration remains manual. After accountable review, express supported operations in the [workflow configuration contract](configurable-workflows.md), register any new effect adapters, connect authoritative sources and test the resulting controls. The current runtime does not execute arbitrary design graphs. A JSON download from Design studio is not a runtime definition to deploy.

### Inspect a workflow package

Use the guided controls for supported policy settings or the advanced JSON editor for the complete definition. Validation checks the runtime contract; it does not assess whether the chosen limits, roles or approval rules are appropriate for your organisation. Review the assessment's unknowns and required implementation work before exporting the package and Markdown report. Changing a definition requires fresh review and configuration-bound approval in a commissioned runtime.

The execution lab always uses its two bundled definitions in a new temporary database. It does not run the definition edited in Workflow packages, an AI draft or an external business operation. Its reviewer account demonstrates separation of duties in a fixture; it is not human approval of a deployment.

## Local operation and data

Studio binds to loopback and is intended for one operator on a trusted machine. Its browser session checks protect local requests; they do not provide user authentication, tenant separation or a shared-service access model. Do not expose it as a multiuser service or put a public proxy in front of it without implementing those controls.

Design jobs and their source descriptions are held in server memory, with at most eight retained jobs and one active job. Older completed jobs can be evicted, and stopping or restarting Studio clears the job store. Studio does not save prose jobs to disk automatically. Explicit downloads are files retained by your browser, and the configured model service may retain its own records. Export anything you need to keep before stopping the server.

Editor changes, component selections and the current result view are also temporary. Reloading the browser does not restore them or cancel an active server job. Save downloads before refreshing; the current interface has no job-history or cancellation screen.

Studio does not automatically execute generated designs, deploy packages, commission native products or approve risk acceptance. The eighteen-component catalogue and synthetic demonstrations do not establish full-stack acceptance or production readiness. See [validation and evidence](validation.md) for the observed results and remaining independent work.

## If something fails

- **AI design is unavailable:** select an installed, schema-capable model or restart Studio with `--model` to set its default, and confirm the selected Ollama endpoint is running. The other screens remain usable without Ollama.
- **The model times out or a draft is rejected:** preserve your original description, inspect the error and retry after checking model capability and available resources. A rejected draft is not an approved or complete design.
- **Runtime JSON fails validation:** correct the reported contract error using the [workflow contract](configurable-workflows.md#workflow-contract). Natural-language design JSON and executable workflow definitions have different schemas.
- **The browser loses its session after a restart:** reload the Studio page to obtain the new local session.

For command-line equivalents and detailed design limits, see the [workflow designer](workflow-designer.md) and [configurable workflows](configurable-workflows.md).
