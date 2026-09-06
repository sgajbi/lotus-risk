# Getting Started

## Fast Local Loop

Prerequisites, before anything else:

- **Python 3.12 or newer** — `pyproject.toml` requires `>=3.12` and CI pins 3.12
- **`make`** — every documented command uses it; not a default on Windows
- **A `lotus-platform` checkout.** `make check` runs `mesh-contract-validate`, which loads a
  validator from lotus-platform and fails with `FileNotFoundError` without it. It is resolved
  from `LOTUS_PLATFORM_ROOT` if set, otherwise `../lotus-platform`, `./.lotus-platform` or
  `./lotus-platform` — so a sibling checkout beside this repository needs no configuration
- **An activated virtual environment.** `make install` installs into whichever interpreter is
  on `PATH`; it does not create one. On a PEP 668 distribution (Debian/Ubuntu, Fedora,
  Homebrew Python) installing into the system interpreter is refused with
  `externally-managed-environment`. CI does not see this because `actions/setup-python`
  supplies an isolated interpreter.

  ```bash
  # Debian/Ubuntu may need the venv module first: sudo apt install python3-venv
  python3 -m venv .venv
  source .venv/bin/activate
  ```

  ```powershell
  py -3 -m venv .venv
  .venv\Scripts\Activate.ps1
  ```

Install dependencies:

```shell
make install
```

Run the fast local gate:

```powershell
make check
```

Start the API directly:

```powershell
uvicorn src.app.main:app --reload --port 8130
```

Use this path for:

1. contract changes,
2. analytics engine work,
3. docs and repo-context work,
4. focused unit and integration debugging.

## Prod-Shaped Local Docker Path

Run the local stack:

```powershell
docker compose up --build
```

This is the better path when you need:

1. local container parity,
2. upstream URL validation,
3. readiness and ops behavior,
4. stateful workflow exercise against local upstreams.

## Canonical Local URLs

For host-based local validation, use:

1. [lotus-risk local API](http://localhost:8130),
2. [lotus-performance local API](http://localhost:8002),
3. [lotus-core query control-plane](http://localhost:8202).

Important rule:

1. `LOTUS_PERFORMANCE_BASE_URL` must point to `lotus-performance`, not a `lotus-core` port.

## First Checks

After startup, inspect:

1. `/health`
2. `/health/live`
3. `/health/ready`
4. `/metadata`
5. `/version`
6. `/ops`
7. `/docs`

## Live Validation Default

The canonical live validation baseline is:

1. portfolio `PB_SG_GLOBAL_BAL_001`
2. as-of date `2026-03-31`

Do not overstate enterprise coverage beyond that baseline unless the live validation matrix has
real seeded archetype IDs and attached evidence.

## Read Next

1. use [Validation and CI](Validation-and-CI) for gate meanings,
2. use [Operations Runbook](Operations-Runbook) for runtime and upstream checks,
3. use [Troubleshooting](Troubleshooting) when local startup or stateful workflows misbehave.
