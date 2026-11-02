# ADR-003: distinguish implementation from native evidence

**Status:** accepted.

## Context

A product name, configuration file, imported SDK or successful health endpoint can create a misleading impression of complete integration.

## Decision

For each of the 18 component groups, provide implementation, deployment and acceptance paths. Record `PASS`, `FAIL` or `BLOCKED` from real operations. Contract tests are reported separately. Missing privileges or credentials remain explicit blockers.

## Consequences

The full native stack is currently unverified in this environment. It cannot inherit the original core's test status. This distinction remains prominent in the README, paper and machine-readable evidence.
