"""The finish fallback as a pure function: the Layer 5 edge cases."""

import pytest

from app.game.finish import assign_leftovers

MEMBERS = [1, 2, 3]  # join order


def totals(assignments, chores, start=None):
    result = dict(start or {})
    effort = dict(chores)
    for chore, member in assignments.items():
        result[member] = result.get(member, 0) + effort[chore]
    return result


def test_nobody_bid_on_anything():
    chores = [(10, 8), (11, 5), (12, 4), (13, 3)]

    assignments = assign_leftovers(chores, MEMBERS, {})

    # 8 -> member 1, 5 -> 2, 4 -> 3, then 3 goes to the lowest total (member 3 on 4).
    assert assignments == {10: 1, 11: 2, 12: 3, 13: 3}
    assert totals(assignments, chores) == {1: 8, 2: 5, 3: 7}


def test_one_member_hoarded_at_auction():
    # Member 1 won 20 effort of chores; the leftovers go to the others.
    chores = [(10, 6), (11, 6)]

    assignments = assign_leftovers(chores, MEMBERS, {1: 20})

    assert set(assignments.values()) == {2, 3}


def test_tie_goes_to_whoever_joined_first():
    assert assign_leftovers([(10, 5)], MEMBERS, {1: 3, 2: 3, 3: 3}) == {10: 1}
    assert assign_leftovers([(10, 5)], MEMBERS, {1: 4, 2: 3, 3: 3}) == {10: 2}


def test_single_member_gets_everything():
    assert assign_leftovers([(10, 5), (11, 2)], [7], {}) == {10: 7, 11: 7}


def test_nothing_left_to_assign():
    assert assign_leftovers([], MEMBERS, {1: 4}) == {}


def test_every_chore_is_assigned_even_when_totals_cannot_balance():
    chores = [(10, 10), (11, 1)]  # 11 effort can never split evenly three ways

    assignments = assign_leftovers(chores, MEMBERS, {})

    assert set(assignments) == {10, 11}


def test_no_members_is_an_error():
    with pytest.raises(ValueError):
        assign_leftovers([(10, 5)], [], {})


def test_result_does_not_depend_on_input_order():
    chores = [(10, 4), (11, 4), (12, 9)]

    assert assign_leftovers(chores, MEMBERS, {}) == assign_leftovers(list(reversed(chores)), MEMBERS, {})
