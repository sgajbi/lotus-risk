from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
import hashlib
import json
from typing import Any

from app.evidence.idea_opportunity_constants import (
    CANONICAL_AS_OF_DATE,
    CANONICAL_PORTFOLIO_ID,
    CANONICAL_PORTFOLIO_REF,
    CONSUMER_BLOCKERS_SATISFIED,
    EXPECTED_EXECUTIONS,
    EXPECTED_NON_PROOF_CLAIMS,
    EXPECTED_RECEIPT_KEYS,
    EXPECTED_SUMMARY_KEYS,
    PROOF_FAMILY,
    REMAINING_CERTIFICATION_BLOCKERS,
    RUNTIME_BOUNDARY,
    SCHEMA_VERSION,
)

ExecutionCallable = Callable[[str, Mapping[str, Any]], tuple[int, Mapping[str, Any]]]


def sha256_json(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def identity_hash(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.strip().encode('utf-8')).hexdigest()}"


def format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("generated_at_utc must be timezone-aware")
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_idea_opportunity_runtime_evidence(
    *,
    execute: ExecutionCallable,
    generated_at_utc: datetime,
    portfolio_id: str = CANONICAL_PORTFOLIO_ID,
    as_of_date: date = CANONICAL_AS_OF_DATE,
) -> dict[str, Any]:
    if portfolio_id != CANONICAL_PORTFOLIO_ID:
        raise ValueError("Idea opportunity runtime evidence is only valid for PB_SG_GLOBAL_BAL_001")
    if as_of_date != CANONICAL_AS_OF_DATE:
        raise ValueError(
            "Idea opportunity runtime evidence is only valid for as-of date 2026-06-21"
        )
    generated_at = format_utc(generated_at_utc)
    portfolio_digest = identity_hash(portfolio_id)
    executions = [
        _build_execution(
            execute=execute,
            route="/analytics/risk/concentration",
            product_id="lotus-risk:ConcentrationRiskReport:v1",
            proof_name="concentration_risk",
            request_payload=_concentration_payload(),
            as_of_date=as_of_date,
            portfolio_digest=portfolio_digest,
            summary_builder=_concentration_summary,
        ),
        _build_execution(
            execute=execute,
            route="/analytics/risk/calculate",
            product_id="lotus-risk:RiskMetricsReport:v1",
            proof_name="high_volatility",
            request_payload=_risk_metrics_payload(as_of_date),
            as_of_date=as_of_date,
            portfolio_digest=portfolio_digest,
            summary_builder=_risk_metrics_summary,
        ),
        _build_execution(
            execute=execute,
            route="/analytics/risk/drawdown",
            product_id="lotus-risk:DrawdownAnalyticsReport:v1",
            proof_name="drawdown_review",
            request_payload=_drawdown_payload(as_of_date),
            as_of_date=as_of_date,
            portfolio_digest=portfolio_digest,
            summary_builder=_drawdown_summary,
        ),
    ]
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": "lotus-risk",
        "evidenceClass": "runtime_execution",
        "proofFamily": PROOF_FAMILY,
        "runtimeBoundary": RUNTIME_BOUNDARY,
        "sourceAuthority": "lotus-risk",
        "generatedAtUtc": generated_at,
        "portfolioBinding": {
            "canonicalPortfolioRef": CANONICAL_PORTFOLIO_REF,
            "portfolioIdentityDigest": portfolio_digest,
            "rawPortfolioIdIncluded": False,
        },
        "executions": executions,
        "consumerBlockersSatisfied": list(CONSUMER_BLOCKERS_SATISFIED),
        "remainingCertificationBlockers": list(REMAINING_CERTIFICATION_BLOCKERS),
        "nonProofClaims": dict(EXPECTED_NON_PROOF_CLAIMS),
    }
    payload["evidenceDigest"] = sha256_json(
        {k: v for k, v in payload.items() if k != "evidenceDigest"}
    )
    return payload


def idea_opportunity_runtime_evidence_is_valid(payload: Mapping[str, Any]) -> bool:
    expected_keys = {
        "schemaVersion",
        "repository",
        "evidenceClass",
        "proofFamily",
        "runtimeBoundary",
        "sourceAuthority",
        "generatedAtUtc",
        "portfolioBinding",
        "executions",
        "consumerBlockersSatisfied",
        "remainingCertificationBlockers",
        "nonProofClaims",
        "evidenceDigest",
    }
    if set(payload) != expected_keys:
        return False
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        return False
    if payload.get("repository") != "lotus-risk" or payload.get("sourceAuthority") != "lotus-risk":
        return False
    if (
        payload.get("evidenceClass") != "runtime_execution"
        or payload.get("proofFamily") != PROOF_FAMILY
    ):
        return False
    if payload.get("runtimeBoundary") != RUNTIME_BOUNDARY:
        return False
    if _parse_utc(payload.get("generatedAtUtc")) is None:
        return False
    if not _portfolio_binding_is_valid(payload.get("portfolioBinding")):
        return False
    if tuple(payload.get("consumerBlockersSatisfied") or ()) != CONSUMER_BLOCKERS_SATISFIED:
        return False
    if (
        tuple(payload.get("remainingCertificationBlockers") or ())
        != REMAINING_CERTIFICATION_BLOCKERS
    ):
        return False
    if not _claims_are_valid(payload.get("nonProofClaims")):
        return False
    executions = payload.get("executions")
    if not isinstance(executions, list) or len(executions) != 3:
        return False
    if not all(_execution_is_valid(execution) for execution in executions):
        return False
    if {execution.get("proofName") for execution in executions} != set(EXPECTED_EXECUTIONS):
        return False
    expected_digest = sha256_json({k: v for k, v in payload.items() if k != "evidenceDigest"})
    return payload.get("evidenceDigest") == expected_digest


def _build_execution(
    *,
    execute: ExecutionCallable,
    route: str,
    product_id: str,
    proof_name: str,
    request_payload: Mapping[str, Any],
    as_of_date: date,
    portfolio_digest: str,
    summary_builder: Callable[[Mapping[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    status_code, response = execute(route, request_payload)
    summary = summary_builder(response) if status_code == 200 else {}
    receipt = {
        "productId": product_id,
        "route": route,
        "statusCode": status_code,
        "asOfDate": as_of_date.isoformat(),
        "portfolioIdentityDigest": portfolio_digest,
        "requestPayloadDigest": sha256_json(request_payload),
        "normalizedResponseDigest": sha256_json(summary),
        "supportabilityState": _supportability_state(response),
        "freshnessBucket": _freshness_bucket(response),
        "summary": summary,
    }
    return {"proofName": proof_name, "receipt": receipt, "receiptDigest": sha256_json(receipt)}


def _risk_metrics_payload(as_of_date: date) -> dict[str, Any]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": as_of_date.isoformat(), "net_or_gross": "NET"},
            "portfolio_open_date": "2026-01-01",
            "periods": [{"type": "YTD", "name": "YTD"}],
            "metrics": ["VOLATILITY", "DRAWDOWN", "VAR", "TRACKING_ERROR"],
            "options": {"frequency": "DAILY", "use_log_returns": False},
            "returns": _return_points((1.5, -2.8, 1.1, -1.6, 0.4)),
            "benchmark_returns": _return_points((0.4, -0.5, 0.3, -0.4, 0.1)),
        },
    }


def _drawdown_payload(as_of_date: date) -> dict[str, Any]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "scope": {"as_of_date": as_of_date.isoformat(), "net_or_gross": "NET"},
            "periods": [{"type": "YTD", "name": "YTD"}],
            "returns": _return_points((1.0, -8.0, -4.0, 2.0, 1.0)),
            "benchmark_returns": _return_points((0.2, -1.0, -0.5, 0.5, 0.3)),
        },
        "analysis_options": {"include_underwater_series": False, "include_episode_list": True},
    }


def _concentration_payload() -> dict[str, Any]:
    return {
        "input_mode": "stateless",
        "stateless_input": {
            "current_positions": [
                {
                    "security_id": "SOURCE_SAFE_POSITION_1",
                    "market_value_base": 55,
                    "issuer_id": "SOURCE_SAFE_ISSUER_A",
                },
                {
                    "security_id": "SOURCE_SAFE_POSITION_2",
                    "market_value_base": 25,
                    "issuer_id": "SOURCE_SAFE_ISSUER_A",
                },
                {
                    "security_id": "SOURCE_SAFE_POSITION_3",
                    "market_value_base": 20,
                    "issuer_id": "SOURCE_SAFE_ISSUER_B",
                },
            ],
            "projected_positions": [
                {
                    "security_id": "SOURCE_SAFE_POSITION_1",
                    "projected_market_value_base": 45,
                    "issuer_id": "SOURCE_SAFE_ISSUER_A",
                },
                {
                    "security_id": "SOURCE_SAFE_POSITION_2",
                    "projected_market_value_base": 20,
                    "issuer_id": "SOURCE_SAFE_ISSUER_A",
                },
                {
                    "security_id": "SOURCE_SAFE_POSITION_3",
                    "projected_market_value_base": 35,
                    "issuer_id": "SOURCE_SAFE_ISSUER_B",
                },
            ],
            "top_n": 2,
        },
    }


def _return_points(values: tuple[float, ...]) -> list[dict[str, Any]]:
    return [
        {"date": f"2026-06-{17 + index:02d}", "value": value} for index, value in enumerate(values)
    ]


def _risk_metrics_summary(response: Mapping[str, Any]) -> dict[str, Any]:
    ytd = _period(response, "YTD")
    metrics = ytd.get("metrics", {}) if isinstance(ytd, Mapping) else {}
    return {
        "periodName": "YTD",
        "volatilityPercent": _metric_value(metrics, "VOLATILITY"),
        "maxDrawdownPercent": _metric_value(metrics, "DRAWDOWN"),
        "varPercent": _metric_value(metrics, "VAR"),
        "trackingErrorPercent": _metric_value(metrics, "TRACKING_ERROR"),
    }


def _drawdown_summary(response: Mapping[str, Any]) -> dict[str, Any]:
    ytd = _period(response, "YTD")
    summary = ytd.get("summary", {}) if isinstance(ytd, Mapping) else {}
    return {
        "periodName": "YTD",
        "maxDrawdown": summary.get("max_drawdown"),
        "timeUnderWaterDays": summary.get("time_under_water_days"),
        "ulcerIndex": summary.get("ulcer_index"),
        "episodeCount": len(ytd.get("episodes", [])) if isinstance(ytd, Mapping) else 0,
    }


def _concentration_summary(response: Mapping[str, Any]) -> dict[str, Any]:
    risk_proxy = response.get("risk_proxy", {})
    issuer = response.get("issuer_concentration", {})
    return {
        "positionHhiCurrent": (
            risk_proxy.get("hhi_current") if isinstance(risk_proxy, Mapping) else None
        ),
        "positionHhiProposed": (
            risk_proxy.get("hhi_proposed") if isinstance(risk_proxy, Mapping) else None
        ),
        "issuerHhiCurrent": issuer.get("hhi_current") if isinstance(issuer, Mapping) else None,
        "issuerHhiProposed": issuer.get("hhi_proposed") if isinstance(issuer, Mapping) else None,
        "topIssuerWeightCurrent": (
            issuer.get("top_issuer_weight_current") if isinstance(issuer, Mapping) else None
        ),
        "coverageStatus": issuer.get("coverage_status") if isinstance(issuer, Mapping) else None,
        "coverageRatioCurrent": issuer.get("coverage_ratio_current")
        if isinstance(issuer, Mapping)
        else None,
    }


def _period(response: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    results = response.get("results", {})
    value = results.get(name) if isinstance(results, Mapping) else None
    return value if isinstance(value, Mapping) else {}


def _metric_value(metrics: Mapping[str, Any], name: str) -> Any:
    metric = metrics.get(name)
    return metric.get("value") if isinstance(metric, Mapping) else None


def _supportability_state(response: Mapping[str, Any]) -> str | None:
    metadata = response.get("metadata", {})
    supportability = (
        metadata.get("calculation_supportability") if isinstance(metadata, Mapping) else None
    )
    return supportability.get("state") if isinstance(supportability, Mapping) else None


def _freshness_bucket(response: Mapping[str, Any]) -> str | None:
    metadata = response.get("metadata", {})
    supportability = (
        metadata.get("calculation_supportability") if isinstance(metadata, Mapping) else None
    )
    return supportability.get("freshness_bucket") if isinstance(supportability, Mapping) else None


def _portfolio_binding_is_valid(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("canonicalPortfolioRef") == CANONICAL_PORTFOLIO_REF
        and value.get("portfolioIdentityDigest") == identity_hash(CANONICAL_PORTFOLIO_ID)
        and value.get("rawPortfolioIdIncluded") is False
    )


def _claims_are_valid(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return dict(value) == EXPECTED_NON_PROOF_CLAIMS


def _execution_is_valid(value: Any) -> bool:
    if not isinstance(value, Mapping) or set(value) != {"proofName", "receipt", "receiptDigest"}:
        return False
    receipt = value.get("receipt")
    if not isinstance(receipt, Mapping):
        return False
    summary = receipt.get("summary")
    return (
        set(receipt) == EXPECTED_RECEIPT_KEYS
        and receipt.get("statusCode") == 200
        and _execution_product_route_is_valid(value)
        and receipt.get("supportabilityState") == "ready"
        and receipt.get("freshnessBucket") == "current"
        and receipt.get("asOfDate") == CANONICAL_AS_OF_DATE.isoformat()
        and receipt.get("portfolioIdentityDigest") == identity_hash(CANONICAL_PORTFOLIO_ID)
        and receipt.get("requestPayloadDigest") == _expected_request_payload_digest(value)
        and _is_sha256(receipt.get("normalizedResponseDigest"))
        and _summary_is_valid(str(value.get("proofName")), summary)
        and receipt.get("normalizedResponseDigest") == sha256_json(summary)
        and value.get("receiptDigest") == sha256_json(receipt)
    )


def _summary_is_valid(proof_name: str, summary: Any) -> bool:
    if not isinstance(summary, Mapping):
        return False
    required_keys = EXPECTED_SUMMARY_KEYS.get(proof_name)
    if required_keys is None:
        return False
    return set(summary) == set(required_keys) and all(
        summary.get(key) is not None for key in required_keys
    )


def _expected_request_payload_digest(value: Mapping[str, Any]) -> str | None:
    proof_name = str(value.get("proofName"))
    if proof_name == "concentration_risk":
        return sha256_json(_concentration_payload())
    if proof_name == "high_volatility":
        return sha256_json(_risk_metrics_payload(CANONICAL_AS_OF_DATE))
    if proof_name == "drawdown_review":
        return sha256_json(_drawdown_payload(CANONICAL_AS_OF_DATE))
    return None


def _execution_product_route_is_valid(value: Mapping[str, Any]) -> bool:
    receipt = value.get("receipt")
    if not isinstance(receipt, Mapping):
        return False
    expected = EXPECTED_EXECUTIONS.get(str(value.get("proofName")))
    return (
        expected is not None
        and receipt.get("productId") == expected[0]
        and receipt.get("route") == expected[1]
    )


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 71 and value.startswith("sha256:")


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None
