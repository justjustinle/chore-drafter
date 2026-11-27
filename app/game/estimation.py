"""Pure estimation logic: no database, no HTTP. Easy to test on its own."""


def effort_from_votes(points: list[int]) -> int:
    """The average vote, always rounded up, using whole numbers only.

    -(-total // count) is "ceiling division": // rounds down, so dividing
    the negative total rounds towards minus infinity, and negating it
    again gives the rounded-up answer. No floats, so no rounding surprises.
    """
    if not points:
        raise ValueError("Cannot work out effort from zero votes")
    total = sum(points)
    count = len(points)
    return -(-total // count)


def everyone_has_voted(voter_ids: set[int], chore_ids: set[int], votes: set[tuple[int, int]]) -> bool:
    """True when every voter has a vote on every chore.

    `votes` holds (member_id, chore_id) pairs.
    """
    return all((member, chore) in votes for member in voter_ids for chore in chore_ids)
