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

Do not place secrets, bearer tokens, or credentials in capability rules, feature flags, base URLs,
logs, examples, or committed environment files.

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
