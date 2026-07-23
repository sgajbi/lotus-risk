from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
try:
    from scripts._repo_imports import force_repo_src_first  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - direct script execution path
    from _repo_imports import force_repo_src_first  # type: ignore[import-not-found,no-redef]  # noqa: E402

force_repo_src_first(PROJECT_ROOT)

from app.evidence.idea_opportunity_runtime import (  # noqa: E402
    build_idea_opportunity_runtime_evidence,
    idea_opportunity_runtime_evidence_is_valid,
)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate source-safe runtime evidence for Idea opportunity archetypes."
    )
    parser.add_argument("--risk-base-url", default="http://localhost:8130")
    parser.add_argument("--portfolio-id", default="PB_SG_GLOBAL_BAL_001")
    parser.add_argument("--as-of-date", default="2026-06-21")
    parser.add_argument("--generated-at-utc", required=True)
    parser.add_argument(
        "--output",
        default="output/idea-opportunity-runtime-evidence/idea-risk-runtime-evidence.json",
    )
    return parser.parse_args(argv)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _execute(
    client: httpx.Client, route: str, payload: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    response = client.post(route, json=payload)
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {"error": "non_json_response"}
    return response.status_code, body


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output = Path(args.output)
    with httpx.Client(base_url=args.risk_base_url, timeout=10.0) as client:
        payload = build_idea_opportunity_runtime_evidence(
            execute=lambda route, body: _execute(client, route, dict(body)),
            generated_at_utc=_parse_datetime(args.generated_at_utc),
            portfolio_id=args.portfolio_id,
            as_of_date=date.fromisoformat(args.as_of_date),
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not idea_opportunity_runtime_evidence_is_valid(payload):
        print(f"Generated evidence failed contract validation: {output}")
        return 1
    print(f"Idea opportunity runtime evidence written: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
