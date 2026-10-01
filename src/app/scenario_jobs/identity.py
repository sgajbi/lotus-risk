from __future__ import annotations

import hashlib
import json

from app.scenario_jobs.contracts import RegimeScenarioPackJobRequest
from app.services.scenario_pack_catalog import SCENARIO_PACKS


def canonical_request_fingerprint(request: RegimeScenarioPackJobRequest) -> str:
    serialized = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def scenario_pack_revision(scenario_pack_id: str) -> str:
    """Return the immutable revision of the exact code-defined pack selected at admission."""
    scenario_pack = SCENARIO_PACKS[scenario_pack_id]
    canonical_pack = [
        {
            "scenario_id": scenario.scenario_id,
            "display_name": scenario.display_name,
            "shock_by_bucket": dict(sorted(scenario.shock_by_bucket.items())),
        }
        for scenario in scenario_pack
    ]
    serialized = json.dumps(canonical_pack, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def normalize_idempotency_key(value: str | None) -> str:
    normalized = value.strip() if value is not None else ""
    if not normalized:
        raise ValueError("Idempotency-Key is required for scenario evaluation job submission")
    if len(normalized) > 128:
        raise ValueError("Idempotency-Key must not exceed 128 characters after trimming")
    return normalized


__all__ = ["canonical_request_fingerprint", "normalize_idempotency_key", "scenario_pack_revision"]
