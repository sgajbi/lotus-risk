from __future__ import annotations

import pytest

from tests.support.live_drawdown_reconciliation import wealth_drawdown

pytestmark = pytest.mark.governance


def test_live_drawdown_oracle_preserves_initial_loss_from_unit_opening_wealth() -> None:
    assert wealth_drawdown([-0.02, 0.01]) == pytest.approx([-0.02, -0.0102])
