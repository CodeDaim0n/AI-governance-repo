# ADR-001: one central business-policy authority

**Status:** accepted for the reference implementation.

## Context

An agent runtime may enforce local restrictions, but competing copies of business policy can drift. A local allow must not bypass enterprise limits.

## Decision

Use Microsoft AGT for tool interception and OPA for central business restrictions. Both can deny. An AGT allow only permits submission to the independently authenticated gateway. Native relationship, data, validation and inventory checks remain mandatory where configured.

## Consequences

The gateway must be the only write path. Policy outages deny new writes and can affect availability. Production must qualify policy-bundle integrity, source freshness and fallback capacity.
