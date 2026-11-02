# Security policy

This is a research prototype with synthetic data, not a supported production security product. Production suitability, legal applicability and independent validation are not established.

## Reporting

Do not publish exploit details with sensitive data in a public issue. Use GitHub private vulnerability reporting if the repository owner has enabled it. Otherwise contact the repository owner through GitHub to agree a private channel before sharing sensitive details. No monitored security mailbox or response SLA is implied.

## Sensitive material

Never commit `.local/`, tokens, client secrets, private signing keys, unseal material, customer records or full model prompts/traces. The example credential file contains empty values only. Any suspected exposure requires revocation and incident handling, not just removing the text from a later commit.

## Known limitations

See [the validation guide](docs/validation.md), [deployment guide](docs/deployment/full-stack.md), [risk register](docs/risk-register.json) and [operations runbook](docs/runbooks/operations.md). The native deployment uses dedicated-lab development settings. All 18 live integrations remain unverified in the current constrained environment.
