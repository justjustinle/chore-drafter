"""Pure estimation maths: no database, no HTTP."""

import pytest

from app.game.estimation import effort_from_votes, everyone_has_voted


@pytest.mark.parametrize(
    ("votes", "expected"),
    [
        ([5], 5),
        ([4, 4], 4),
        ([4, 5], 5),  # 4.5 rounds up
        ([1, 1, 2], 2),  # 1.33 rounds up
        ([10, 10, 9], 10),  # 9.67 rounds up
        ([3, 3, 3, 4], 4),  # 3.25 rounds up: always up, never to nearest
        ([1, 10], 6),  # 5.5 rounds up
    ],
)
def test_effort_is_average_rounded_up(votes, expected):
    assert effort_from_votes(votes) == expected


def test_effort_with_no_votes_is_an_error():
    with pytest.raises(ValueError):
        effort_from_votes([])


def test_everyone_has_voted():
    voters = {1, 2}
    chores = {10, 20}
    all_votes = {(1, 10), (1, 20), (2, 10), (2, 20)}

    assert everyone_has_voted(voters, chores, all_votes)
    assert not everyone_has_voted(voters, chores, all_votes - {(2, 20)})
