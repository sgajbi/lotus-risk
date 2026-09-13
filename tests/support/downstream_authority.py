"""Shared already-admitted authority values for tests.

Direct DownstreamAuthority construction is sanctioned only here and in tests:
production code must admit through admit_downstream_authority.
"""

from __future__ import annotations

from app.contracts.downstream_authority import DownstreamAuthority

TEST_TENANT_ID = "tenant-a"


def admitted_test_authority(
    correlation_id: str | None = None,
    *,
    tenant_id: str = TEST_TENANT_ID,
) -> DownstreamAuthority:
    return DownstreamAuthority(tenant_id=tenant_id, correlation_id=correlation_id)
