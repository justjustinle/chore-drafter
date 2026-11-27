"""Pure auction logic: no database, no HTTP.

`order` is always the list of member ids in turn order, e.g. [1, 2, 3].
"Rotation" means after the last member comes the first again.
"""

from datetime import datetime, timedelta

from app.game.rules import STARTING_TOKENS


def tokens_left(chores_nominated: int, tokens_spent: int) -> int:
    """Budget = 100 + 1 per chore nominated so far this week − tokens spent."""
    return STARTING_TOKENS + chores_nominated - tokens_spent


def next_in_rotation(order: list[int], after: int) -> int:
    """The member who comes after `after` (wrapping round to the start)."""
    position = order.index(after)
    return order[(position + 1) % len(order)]


def next_bidder(order: list[int], after: int, passed: set[int], high_bidder: int) -> int | None:
    """Who bids next: the first member after `after` who has not passed and
    is not the current high bidder. None means everyone else has passed,
    so the chore is sold."""
    member = after
    for _ in range(len(order)):
        member = next_in_rotation(order, member)
        if member not in passed and member != high_bidder:
            return member
    return None


def skip_timed_out_nominations(
    order: list[int], nominator: int, deadline: datetime, now: datetime, turn_seconds: int
) -> tuple[int, int, datetime]:
    """Nomination turns that ran out while nobody was asking.

    Each missed turn passes the nomination to the next member and starts a
    fresh 30 seconds. Instead of looping once per missed turn (a server left
    idle for a day would loop thousands of times), work out how many turns
    were missed with division.

    Returns (who nominates now, how many turns were skipped, their deadline).
    """
    if now <= deadline:
        return nominator, 0, deadline
    turn = timedelta(seconds=turn_seconds)
    skipped = (now - deadline) // turn + 1
    position = (order.index(nominator) + skipped) % len(order)
    return order[position], skipped, deadline + skipped * turn


def first_nominator(order: list[int], week_index: int) -> int:
    """The first nominator rotates each week: week 0 starts with the first
    member, week 1 with the second, and so on."""
    return order[week_index % len(order)]
