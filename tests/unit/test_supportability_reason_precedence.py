"""The precedence covers its own declared domain, and says so if it stops (#281).

`select_supportability_reason` accepts any `RiskSupportabilityReason` and ranked
four of the ten. The other six exhausted a `next()` with no default, so every
value the signature declared as acceptable except four raised a bare
`StopIteration`.

It never crashed, and the reason it never crashed is the finding: the two call
sites both pass `degraded_reasons`, which is filled by exactly two producers
whose returns happen to be the four ranked values. The function was safe by
coincidence of who called it, not by anything it did or declared.

The annotation is what hid it. `tuple[RiskSupportabilityReason, ...]` rejects a
**wrong** member and accepts a **short** one, so it looks like it ties the tuple
to the alias and does not.

That gap widened while this issue sat open. `group_return_series_unavailable`
was added to the alias for #283 -- by me -- and went unranked, which is exactly
mechanism 1 in the issue: a member added to the alias with nothing linking it to
the precedence.
"""

from __future__ import annotations

from typing import get_args

import pytest

from app.contracts.risk import RiskSupportabilityReason
from app.services.supportability_periods import (
    _NOT_A_DEGRADATION_REASON,
    _SUPPORTABILITY_REASON_PRECEDENCE,
    select_supportability_reason,
)

ALL_REASONS = frozenset(get_args(RiskSupportabilityReason))


def test_every_declared_reason_is_ranked_or_explicitly_excluded() -> None:
    """The invariant, rather than a list of the members that exist today.

    Asserting a hand-written expected set here would be a third copy of the
    alias, and it would need editing every time the domain grows -- which is the
    failure being fixed, one level up. This derives both sides and fails on a
    member that is in neither collection.
    """
    ranked = frozenset(_SUPPORTABILITY_REASON_PRECEDENCE)

    unaccounted = ALL_REASONS - ranked - _NOT_A_DEGRADATION_REASON
    assert not unaccounted, (
        f"{sorted(unaccounted)} are declared reasons with no precedence and no "
        "recorded exclusion; rank them or add them to _NOT_A_DEGRADATION_REASON "
        "with the reason"
    )


def test_a_reason_is_not_both_ranked_and_excluded() -> None:
    """The other half of the partition.

    Without this, adding a member to both collections would satisfy the coverage
    test while leaving the exclusion comment describing something that is in
    fact selectable.
    """
    assert not frozenset(_SUPPORTABILITY_REASON_PRECEDENCE) & _NOT_A_DEGRADATION_REASON


def test_nothing_outside_the_alias_is_ranked() -> None:
    """A typo'd rank is dead weight that no input can ever match.

    The annotation already refuses a wrong literal, so this is belt-and-braces
    -- but the annotation also refused nothing about the short tuple, which is
    how this issue arose.
    """
    assert frozenset(_SUPPORTABILITY_REASON_PRECEDENCE) <= ALL_REASONS
    assert _NOT_A_DEGRADATION_REASON <= ALL_REASONS


def test_the_precedence_has_no_duplicates() -> None:
    """A repeated member means one of the two placements is unreachable."""
    ranked = list(_SUPPORTABILITY_REASON_PRECEDENCE)

    assert len(ranked) == len(set(ranked))


@pytest.mark.parametrize("reason", sorted(ALL_REASONS - {"calculation_complete"}))
def test_every_degradation_reason_selects_itself_when_alone(
    reason: RiskSupportabilityReason,
) -> None:
    """Each of the ten, driven through the real function.

    Six of these raised `StopIteration` before. Parameterised over the alias
    rather than a written list, so a new member is exercised the day it is
    added.
    """
    assert select_supportability_reason([reason]) == reason


def test_the_original_four_keep_their_relative_order() -> None:
    """Ranking six more reasons must not reorder the four that were already there.

    The existing order is real domain content and other tests depend on it: a
    missing benchmark outranks an alignment failure, which outranks a shortfall,
    which outranks a self-reported quality flag. Inserting around them is safe;
    reordering them is a behaviour change wearing a refactor's clothes.
    """
    ranked = list(_SUPPORTABILITY_REASON_PRECEDENCE)
    original = [
        "benchmark_unavailable",
        "insufficient_aligned_observations",
        "insufficient_observations",
        "calculation_quality_issue",
    ]

    assert [reason for reason in ranked if reason in original] == original


def test_the_most_severe_reason_wins_across_the_whole_domain() -> None:
    """Selection is by rank, not by input order or set iteration order.

    Passing every degradation reason at once must yield the first ranked one.
    A `set` is built inside the function, so an implementation that leaked set
    ordering would pass a two-element test and fail here.
    """
    every_degradation = [
        reason for reason in ALL_REASONS if reason not in _NOT_A_DEGRADATION_REASON
    ]

    assert select_supportability_reason(every_degradation) == _SUPPORTABILITY_REASON_PRECEDENCE[0]
    assert (
        select_supportability_reason(list(reversed(every_degradation)))
        == _SUPPORTABILITY_REASON_PRECEDENCE[0]
    )


def test_an_unrankable_reason_names_itself_and_the_function() -> None:
    """The failure mode, replaced.

    `StopIteration` carried neither the value nor this module, and inside a
    generator or `async` frame PEP 479 rewrites it to
    `RuntimeError: generator raised StopIteration`, which points at neither.
    """
    with pytest.raises(ValueError, match="select_supportability_reason has no precedence"):
        select_supportability_reason(["not_a_declared_reason"])  # type: ignore[list-item]


def test_an_empty_sequence_is_refused_rather_than_crashing() -> None:
    """No reasons is not a reason.

    Previously `StopIteration`; a caller reaching here has decided a response is
    degraded without recording why, and should be told that.
    """
    with pytest.raises(ValueError, match="no precedence"):
        select_supportability_reason([])
