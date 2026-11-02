# Component catalogue

The expanded implementation covers all **18 component groups** below. Native clients, deployment/provisioning code and acceptance operations are supplied. None is represented as live-integrated merely because code exists. See [validation](../validation.md) and the machine-readable live result.

| ID | Component | Native responsibility | Guide |
| --- | --- | --- | --- |
| 01 | Keycloak | Verified service-account JWT identity | [Reference](01-keycloak.md) |
| 02 | Microsoft Agent Governance Toolkit | Deterministic agent-side tool interception | [Reference](02-microsoft-agent-governance-toolkit.md) |
| 03 | Open Policy Agent | Business action/context policy | [Reference](03-open-policy-agent.md) |
| 04 | OpenFGA | Record relationship authorization | [Reference](04-openfga.md) |
| 05 | Temporal | Durable workflow, bounded retries and approval waits | [Reference](05-temporal.md) |
| 06 | CISO Assistant Community | Risk register and evidence records | [Reference](06-ciso-assistant-community.md) |
| 07 | OpenMetadata | Data ownership, classification and lineage | [Reference](07-openmetadata.md) |
| 08 | MLflow | Versioned evaluation, candidate and approved release | [Reference](08-mlflow.md) |
| 09 | OpenBao | Separated runtime secret access | [Reference](09-openbao.md) |
| 10 | OpenTelemetry Collector | Minimized exported execution spans | [Reference](10-opentelemetry-collector.md) |
| 11 | Prometheus and Alertmanager | Metrics, rule evaluation and authenticated alert delivery | [Reference](11-prometheus-and-alertmanager.md) |
| 12 | DFIR-IRIS | Native incident alert records | [Reference](12-dfir-iris.md) |
| 13 | GLPI | Service inventory and remediation tickets | [Reference](13-glpi.md) |
| 14 | PostgreSQL | Transactional business state, evidence and delivery receipts | [Reference](14-postgresql.md) |
| 15 | Fairlearn | Actual fairness metric computation | [Reference](15-fairlearn.md) |
| 16 | Kubernetes and Cilium | Agent isolation with explicit egress | [Reference](16-kubernetes-and-cilium.md) |
| 17 | Syft, Grype and Cosign | Image inventory, vulnerability gate and offline signing | [Reference](17-syft-grype-and-cosign.md) |
| 18 | Ollama and Qwen | Local proposal generation without execution credentials | [Reference](18-ollama-and-qwen25.md) |

## Established products behind the component map

Official links introduce what each product is; the reference page explains its specific interface and evidence status.

| ID | Official product sources | Role |
| --- | --- | --- |
| 01 | [Keycloak](https://www.keycloak.org/) | Identity and access management providing signed identities and access tokens for agents and reviewers. |
| 02 | [Microsoft Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit) | Runtime governance toolkit intercepting tool calls before they enter our centrally governed execution path. |
| 03 | [Open Policy Agent (OPA)](https://www.openpolicyagent.org/) | Policy engine evaluating deterministic allow/deny rules for actions, budgets, context and operational restrictions. |
| 04 | [OpenFGA](https://openfga.dev/) | Fine-grained authorization service deciding whether a particular agent may act on a particular record. |
| 05 | [Temporal](https://temporal.io/) | Durable workflow engine maintaining process progress, human approval waits and bounded retries. |
| 06 | [CISO Assistant Community](https://github.com/intuitem/ciso-assistant-community) | Governance, risk and compliance platform holding our risk register, control ownership, treatment and linked evidence. |
| 07 | [OpenMetadata](https://open-metadata.org/) | Metadata platform supplying data ownership, classification and lineage for trusted workflow context. |
| 08 | [MLflow](https://mlflow.org/) | Model lifecycle platform connecting versioned evaluation evidence, candidate artifacts and approved release records. |
| 09 | [OpenBao](https://openbao.org/) | Secrets-management platform separating credential access for the gateway, workflow worker and evidence dispatcher. |
| 10 | [OpenTelemetry](https://opentelemetry.io/) | Observability framework exporting minimized execution spans so decisions and outcomes can be traced. |
| 11 | [Prometheus](https://prometheus.io/) · [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) | Monitoring and alerting products turning decision, failure and delivery-backlog metrics into operational signals. |
| 12 | [DFIR-IRIS](https://www.dfir-iris.org/) | Incident-response platform receiving customer-scoped alerts and supporting investigation, containment and recovery. |
| 13 | [GLPI](https://www.glpi-project.org/en/) | IT service-management and asset platform linking workflows to owned services and trackable remediation tickets. |
| 14 | [PostgreSQL](https://www.postgresql.org/) | Transactional database coordinating synthetic business state, shared budgets, approvals, audit records and delivery receipts. |
| 15 | [Fairlearn](https://fairlearn.org/) | Responsible-AI evaluation library calculating group-outcome differences and producing versioned validation evidence. |
| 16 | [Kubernetes](https://kubernetes.io/) · [Cilium](https://cilium.io/) | Workload and network-security platforms isolating the agent and restricting its permitted network routes. |
| 17 | [Syft](https://github.com/anchore/syft) · [Grype](https://github.com/anchore/grype) · [Cosign](https://github.com/sigstore/cosign) | Software-supply-chain tools inventorying built images, checking vulnerabilities and signing/verifying release artifacts. |
| 18 | [Ollama](https://ollama.com/) · [Qwen model](https://huggingface.co/Qwen) | Local agent inference and bounded tool selection; observations drive the next step while the gateway independently authorizes effects. |
