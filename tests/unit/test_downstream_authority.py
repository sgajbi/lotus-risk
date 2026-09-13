"""Admission and header-construction proof for the downstream tenant authority path.

Destination: tests/unit/test_downstream_authority.py
Covers contracts/downstream_authority.py at commit c04aa40 exactly; no service-layer
dependencies, so it is stable while the service threading lands.
"""

from __future__ import annotations

import pytest

from app.contracts.downstream_authority import (
    INVALID_TENANT_AUTHORITY_CODE,
    MAX_TENANT_ID_LENGTH,
    MISSING_TENANT_AUTHORITY_CODE,
    DownstreamAuthority,
    TenantAuthorityError,
    admit_downstream_authority,
    downstream_authority_headers,
    required_downstream_authority,
)


def _admit(tenant_id: str | None) -> DownstreamAuthority:
    return admit_downstream_authority(tenant_id=tenant_id, correlation_id="corr-1")


class TestAdmission:
    def test_valid_tenant_is_admitted_trimmed(self) -> None:
        authority = _admit("  tenant-sg  ")
        assert authority.tenant_id == "tenant-sg"
        assert authority.correlation_id == "corr-1"

    def test_missing_tenant_refuses_401(self) -> None:
        with pytest.raises(TenantAuthorityError) as excinfo:
            _admit(None)
        assert excinfo.value.status_code == 401
        assert excinfo.value.code == MISSING_TENANT_AUTHORITY_CODE

    @pytest.mark.parametrize("blank", ["", "   ", "\t"])
    def test_blank_tenant_refuses_401(self, blank: str) -> None:
        with pytest.raises(TenantAuthorityError) as excinfo:
            _admit(blank)
        assert excinfo.value.status_code == 401
        assert excinfo.value.code == MISSING_TENANT_AUTHORITY_CODE

    def test_oversized_tenant_refuses_400(self) -> None:
        with pytest.raises(TenantAuthorityError) as excinfo:
            _admit("t" * (MAX_TENANT_ID_LENGTH + 1))
        assert excinfo.value.status_code == 400
        assert excinfo.value.code == INVALID_TENANT_AUTHORITY_CODE

    def test_exact_bound_tenant_is_admitted(self) -> None:
        # 128 is the supported bound, not the first refused length.
        assert _admit("t" * MAX_TENANT_ID_LENGTH).tenant_id == "t" * MAX_TENANT_ID_LENGTH

    def test_oversized_before_trim_is_admitted_after_trim(self) -> None:
        padded = " " * 10 + "t" * MAX_TENANT_ID_LENGTH + " " * 10
        assert _admit(padded).tenant_id == "t" * MAX_TENANT_ID_LENGTH


class TestRequiredAuthority:
    def test_none_fails_closed_as_missing(self) -> None:
        with pytest.raises(TenantAuthorityError) as excinfo:
            required_downstream_authority(None)
        assert excinfo.value.status_code == 401

    def test_admitted_value_passes_through(self) -> None:
        authority = _admit("tenant-sg")
        assert required_downstream_authority(authority) is authority


class TestHeaders:
    def test_headers_carry_tenant_and_correlation(self) -> None:
        headers = downstream_authority_headers(_admit("tenant-sg"))
        assert headers == {"X-Tenant-Id": "tenant-sg", "X-Correlation-Id": "corr-1"}

    def test_headers_without_correlation_carry_tenant_only(self) -> None:
        authority = admit_downstream_authority(tenant_id="tenant-sg", correlation_id=None)
        assert downstream_authority_headers(authority) == {"X-Tenant-Id": "tenant-sg"}
