"""Pure auction rules: no database, no HTTP."""

from datetime import datetime, timedelta, timezone

from app.game.auction import (
    first_nominator,
    next_bidder,
    next_in_rotation,
    skip_timed_out_nominations,
    tokens_left,
)

ORDER = [1, 2, 3]
T0 = datetime(2026, 11, 29, 20, 0, tzinfo=timezone.utc)


def test_tokens_left_gets_one_per_nomination():
    assert tokens_left(chores_nominated=0, tokens_spent=0) == 100
    assert tokens_left(chores_nominated=3, tokens_spent=10) == 93


def test_next_in_rotation_wraps_round():
    assert next_in_rotation(ORDER, 1) == 2
    assert next_in_rotation(ORDER, 3) == 1


def test_next_bidder_skips_passed_members_and_the_high_bidder():
    assert next_bidder(ORDER, after=1, passed=set(), high_bidder=1) == 2
    assert next_bidder(ORDER, after=1, passed={2}, high_bidder=1) == 3
    assert next_bidder(ORDER, after=3, passed=set(), high_bidder=1) == 2  # 1 is high bidder


def test_next_bidder_is_none_when_everyone_else_passed():
    assert next_bidder(ORDER, after=2, passed={2, 3}, high_bidder=1) is None


def test_no_nominations_skipped_before_deadline():
    assert skip_timed_out_nominations(ORDER, 1, T0, T0, 30) == (1, 0, T0)


def test_one_missed_nomination_turn():
    member, skipped, deadline = skip_timed_out_nominations(ORDER, 1, T0, T0 + timedelta(seconds=1), 30)
    assert (member, skipped, deadline) == (2, 1, T0 + timedelta(seconds=30))


def test_a_day_of_missed_turns_is_worked_out_without_looping():
    member, skipped, deadline = skip_timed_out_nominations(ORDER, 1, T0, T0 + timedelta(days=1), 30)
    assert skipped == 2881  # 24 * 60 * 2 turns, plus the one that was already running
    assert member == ORDER[(0 + 2881) % 3]
    assert deadline > T0 + timedelta(days=1)


def test_first_nominator_rotates_each_week():
    assert [first_nominator(ORDER, week) for week in range(4)] == [1, 2, 3, 1]
