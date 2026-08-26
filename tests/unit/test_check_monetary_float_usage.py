from __future__ import annotations

import json
from pathlib import Path

from scripts import check_monetary_float_usage

import pytest

pytestmark = pytest.mark.governance


def test_load_allowlist_rejects_legacy_string_entries(tmp_path: Path) -> None:
    allowlist_path = tmp_path / "monetary-float-allowlist.json"
    allowlist_path.write_text(
        json.dumps(
            {
                "allowlist": [
                    "src/app/services/example.py:12:amount: float",
                ]
            }
        ),
        encoding="utf-8",
    )

    entries, errors, stale = check_monetary_float_usage.load_allowlist(allowlist_path)

    assert entries == {}
    assert stale == []
    assert errors == [
        "Legacy allowlist string entry must be migrated: "
        "src/app/services/example.py:12:amount: float"
    ]


def test_scan_repo_ignores_tests_and_explicit_allow_comments(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "app"
    tests_dir = tmp_path / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    (src_dir / "engine.py").write_text(
        "\n".join(
            [
                "approved_amount: float  # monetary-float-allow",
                "unauthorized_amount: float",
            ]
        ),
        encoding="utf-8",
    )
    (tests_dir / "test_engine.py").write_text(
        "amount: float\n",
        encoding="utf-8",
    )

    findings = check_monetary_float_usage.scan_repo(tmp_path)

    assert findings == ["src/app/engine.py:2:unauthorized_amount: float"]


def test_scan_repo_ignores_non_monetary_analytics_float_annotations(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "app"
    src_dir.mkdir(parents=True)

    (src_dir / "analytics.py").write_text(
        "\n".join(
            [
                "rolling_risk: float",
                "benchmark_return: float",
                "position_weight: float",
                "active_exposure: float",
            ]
        ),
        encoding="utf-8",
    )

    findings = check_monetary_float_usage.scan_repo(tmp_path)

    assert findings == []


def test_scan_repo_flags_money_bearing_snake_case_identifiers(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "app"
    src_dir.mkdir(parents=True)

    (src_dir / "portfolio.py").write_text(
        "\n".join(
            [
                "portfolio_market_value: float",
                "cash_balance: float",
                "booking_fee_amount: float",
            ]
        ),
        encoding="utf-8",
    )

    findings = check_monetary_float_usage.scan_repo(tmp_path)

    assert findings == [
        "src/app/portfolio.py:1:portfolio_market_value: float",
        "src/app/portfolio.py:2:cash_balance: float",
        "src/app/portfolio.py:3:booking_fee_amount: float",
    ]
