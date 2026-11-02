# Developer guide

## Layout and responsibility

- `fabric/core.py`: original enforcement invariants and synthetic state transaction.
- `fabric/enterprise/clients.py`: bounded native product APIs; no model-supplied endpoints.
- `fabric/enterprise/postgres.py`: PostgreSQL storage adaptation and serialization guard.
- `fabric/enterprise/app.py`: authenticated native gateway routes and telemetry.
- `fabric/enterprise/workflows.py`: Temporal workflow and token acquisition within activities.
- `fabric/enterprise/dispatch.py`: per-destination evidence/incident delivery receipts.
- `deploy/` and `scripts/`: deployment, commissioning, isolation and acceptance.

## Verification

Run the core suite with a real OPA binary. Run enterprise contract tests with the native dependency set. Build documentation with `mkdocs build --strict`. A native product integration change also needs live acceptance on the commissioned host; a mocked HTTP response cannot provide that evidence.

## Pull request checklist

- State the user-visible or operator-visible problem and resulting behavior.
- Link the affected component and control objective.
- Explain the trust boundary and failure behavior.
- Include the relevant negative assertion and recorded test result.
- Update API, component, deployment or runbook documentation when the interface changes.
- Describe any privileged operation, new external dependency or unverified environment requirement.
- Keep dependency ranges and observed locks distinct; qualify vulnerabilities and licenses for the chosen release.

CODEOWNERS identifies the repository owner for review routing. It does not itself enable protected branches or enforce independent approval.

## Regenerate the research artifact

Install `requirements-docs.txt` and the DejaVu Sans font files used by the PDF script. On the supported Linux authoring environment, run `python scripts/render_paper.py`. It regenerates the paper, Markdown source and three vector diagrams from the retained experiment and component records. Render and visually inspect the result before publishing it.
