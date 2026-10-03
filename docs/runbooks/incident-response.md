# Risk Service Incident Response

This runbook governs the `lotus-risk` service response after a declared monitoring alert. It does
not activate deployment alert routing, assign people, or prove a production exercise.

- Contract posture: `prepared_not_exercised`
- Production acceptance: `false`
- Monitoring severity mapping: `critical=SEV1,warning=SEV2`

## Control Contract

`contracts/observability/lotus-risk-incident-response.v1.json` is the machine-readable source for:

1. incident severity classification;
2. exact mapping of every governed monitoring alert;
3. containment, recovery, reconciliation, escalation roles, and source-safe evidence;
4. credential-response ownership and corrective-action record shape;
5. unresolved deployment and exercise evidence.

Run `make incident-response-contract-validate` from the repository root after changing the
monitoring contract, alert runbooks, or incident policy.

Before creating first or replacement exercise evidence, run
`python scripts/validate_incident_response_contract.py --prepare-exercise-revision` from the
repository root. It validates the bound inputs and prints candidate revisions without accepting the
lifecycle transition.

## Declare And Contain

1. Confirm the alert id and immutable deployed release/image identity.
2. Classify with the contract using the declared monitoring severity mapping above.
3. Resolve named roles through the deployment-controlled contact directory. Do not store personal
   contact data in this repository.
4. Apply only the alert-specific containment. Keep source-dependent calculations fail closed and
   preserve durable job state and claim fences.
5. If identity or credential compromise is suspected, notify the deployment authority to revoke
   and rotate credentials. Never copy credentials into incident evidence.

## Evidence And Communication

Use only the contract allowlist. Do not record tenant, portfolio, account, client, actor,
instrument, idempotency-key, credential, raw payload, or raw-error data. Preserve digests or
bounded references where investigation requires correlation.

An `exercise_plan` and `exercise_result` must record the candidate contract-revision and
response-profile SHA-256 values printed by the `--prepare-exercise-revision` command above. A result
must also reference a source-safe JSON evidence artifact and record its exact byte digest. Its
`exercise_id` and `timestamp_utc` must equal the result identity and `executed_at`, preventing
evidence reuse across exercise results. The contract revision covers incident policy, runbook
content, and canonical monitoring definitions; JSON formatting and platform line endings do not
change its identity.
Earlier or failed results remain history and cannot advance the posture. Plans and valid passes
must cover the selected alert's escalation roles.

Communicate measured impact, affected capability, supportability state, and current containment.
Do not relabel degraded, blocked, unavailable, or unsupported analytics as ready.

## Recover And Reconcile

1. Remediate by reviewed forward-fix or deploy the last accepted immutable image according to the
   deployment change policy.
2. Execute the alert-specific recovery checks in the contract.
3. Independently reconcile financial output or durable state before restoring normal posture.
4. Preserve original failure and replay history; do not delete it to obtain a clean result.
5. Record corrective actions with the governed fields and retain unresolved external blockers.

## Acceptance Boundary

Repository validation proves contract consistency only. Production readiness still requires:

- approved contact assignments and alert routing;
- deployed acknowledgement targets;
- an executed exercise or incident review;
- a deployment-owned corrective-action tracker;
- explicit acceptance by the incident commander and service support owner.

The machine-checked declarations at the top of this runbook state the current contract posture and
production-acceptance decision. Update them in the same change as any evidence-backed lifecycle
transition.
