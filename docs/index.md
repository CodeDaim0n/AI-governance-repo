# Governed Agent Fabric

![Governed Agent Fabric](assets/fabric-banner.svg)

Our domain-independent implementation approach extends the Erdos governance framework across the end-to-end product suite: risk, authority, assurance, action, evidence and response.

![All 18 component groups](assets/system-architecture-18.svg)

Start with the [quickstart](getting-started.md), inspect the [architecture](architecture.md), or open the [18-component catalogue](components/catalogue.md). For a complete installation, follow the [commissioning guide](deployment/full-stack.md).

!!! warning "Evidence boundary"
    The original core has 51 observed checks. The expanded 18-component native deployment is implemented in code but is not verified running here. The available environment has no container or Kubernetes privileges. Read [validation](validation.md) before interpreting any result as assurance.

The [research paper](Governed_Agent_Fabric_Research_Paper.pdf) discusses the rationale, standards, experiment and limitations. The [risk register](risk-register.json), [step/product matrix](step-product-matrix.csv), [integration contracts](integration-contracts.json) and [framework mapping](framework-mapping.csv) are machine-readable companion artifacts.

## Reading paths

- **Architecture and risk:** architecture → component catalogue → design decisions → research paper.
- **Implementation:** quickstart → full deployment → API → live acceptance.
- **Operations:** deployment → operations runbook → security reporting → evidence interpretation.

See [the repository](https://github.com/CodeDaim0n/AI-governance-repo) for code, issues and version history.
