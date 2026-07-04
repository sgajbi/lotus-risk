# Lotus Risk Configuration

`lotus-risk` uses environment variables for runtime configuration. Defaults support local
development and contract generation; enterprise bank deployments must provide the stricter
security posture documented in `docs/security-deployment-policy.md`.

## Downstream Dependencies

| Setting | Default | Purpose |
| --- | --- | --- |
| `LOTUS_CORE_BASE_URL` | `http://core-control.dev.lotus` | `lotus-core` query control-plane base URL |
| `LOTUS_CORE_TIMEOUT_SECONDS` | `10` | Per-request timeout |
| `LOTUS_CORE_MAX_CONNECTIONS` | `100` | Maximum reusable HTTP connections |
| `LOTUS_CORE_MAX_KEEPALIVE_CONNECTIONS` | `20` | Maximum idle keepalive connections |
| `LOTUS_CORE_KEEPALIVE_EXPIRY_SECONDS` | `5` | Idle keepalive expiry |
| `LOTUS_PERFORMANCE_BASE_URL` | `http://performance.dev.lotus` | `lotus-performance` analytics base URL |
| `LOTUS_PERFORMANCE_TIMEOUT_SECONDS` | `10` | Per-request timeout |
| `LOTUS_PERFORMANCE_MAX_CONNECTIONS` | `100` | Maximum reusable HTTP connections |
| `LOTUS_PERFORMANCE_MAX_KEEPALIVE_CONNECTIONS` | `20` | Maximum idle keepalive connections |
| `LOTUS_PERFORMANCE_KEEPALIVE_EXPIRY_SECONDS` | `5` | Idle keepalive expiry |
| `LOTUS_PERFORMANCE_ASYNC_POLL_INTERVAL_SECONDS` | `1` | Delay between async result polls |
| `LOTUS_PERFORMANCE_ASYNC_MAX_POLLS` | `60` | Maximum async result polls |

Downstream base URLs fail fast unless they:

1. use `http` or `https`,
2. include a valid hostname and optional port,
3. exclude embedded credentials,
4. exclude query strings, fragments, whitespace, and control characters.

The service never includes a rejected URL value in the validation error because it may contain
credentials. Production ASGI runtimes must keep lifespan support enabled so connection and
keepalive limits apply to reusable application-owned pools.

Local development keeps permissive fallback semantics for invalid timeout, pool, keepalive, and
async polling overrides: malformed, zero, or negative values fall back to the documented defaults.
Enterprise bank runtime enforcement is stricter. When `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true`,
explicit invalid overrides for `LOTUS_CORE_*`, `LOTUS_PERFORMANCE_*`, or
`LOTUS_PERFORMANCE_ASYNC_*` runtime controls fail application construction with bounded
`invalid_downstream_runtime_setting:<ENV_NAME>` issue codes and never echo configured values.

## Enterprise Security

| Setting | Local default | Enterprise bank posture |
| --- | --- | --- |
| `ENTERPRISE_POLICY_VERSION` | `1.0.0` | Explicit governed policy version |
| `ENTERPRISE_ENFORCE_AUTHZ` | `false` | Must be `true` |
| `ENTERPRISE_ENFORCE_RUNTIME_CONFIG` | `false` | Must be `true` |
| `ENTERPRISE_PRIMARY_KEY_ID` | unset | Required active key identifier |
| `ENTERPRISE_SECRET_ROTATION_DAYS` | `90` | Explicit value from `1` to `90` |
| `ENTERPRISE_CAPABILITY_RULES_JSON` | `{}` | Required endpoint capability map |
| `ENTERPRISE_FEATURE_FLAGS_JSON` | `{}` | Governed feature-flag map where used |
| `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES` | `1048576` | Explicit value aligned to ingress and ASGI limits |
| `ENTERPRISE_INGRESS_MAX_BODY_BYTES` | unset | Required enterprise proof of ingress/proxy body limit |
| `ENTERPRISE_ASGI_MAX_BODY_BYTES` | unset | Required enterprise proof of ASGI/server body limit |

Do not place secrets, bearer tokens, or credentials in capability rules, feature flags, base URLs,
logs, examples, or committed environment files.

When `ENTERPRISE_ENFORCE_RUNTIME_CONFIG=true`, application construction fails closed unless the
enterprise bank posture above is explicit. The failure contains bounded issue codes only and never
includes configuration values.

`ENTERPRISE_INGRESS_MAX_BODY_BYTES` and `ENTERPRISE_ASGI_MAX_BODY_BYTES` are machine-readable
deployment proof values, not application request limits. In enterprise mode, both must be positive
integers at or below `ENTERPRISE_MAX_WRITE_PAYLOAD_BYTES`; otherwise startup fails with bounded
`missing_or_invalid_*_max_body_bytes` or `*_max_body_bytes_exceeds_app_limit` issue codes. The
in-process `Content-Length` check remains defense in depth for write requests, not complete
protection for chunked or streamed bodies.

Capability-rule keys must use `<WRITE_METHOD> /absolute/path-prefix` form with a nonempty string
capability value. When authorization is enabled, write requests without a matching rule fail closed
with `missing_capability_rule`. When multiple prefixes match, the most specific path rule wins.

## Quality-Gate Controls

These settings affect repository validation rather than application runtime:

| Setting | Default | Purpose |
| --- | --- | --- |
| `COVERAGE_FAIL_UNDER` | `98` | Coverage gate threshold |
| `SOURCE_FILE_MAX_LINES` | `450` | Python source-module size ceiling |

## Validation

Use:

```text
make check
make security-audit
```

For canonical local URLs, see `docs/operations/canonical-local-upstream-urls.md`.
