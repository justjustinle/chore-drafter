"""The finish fallback: share out unsold chores so effort evens out.

Pure function: no database, no HTTP.
"""


def assign_leftovers(
    leftovers: list[tuple[int, int]],
    member_order: list[int],
    effort_so_far: dict[int, int],
) -> dict[int, int]:
    """Decide who gets each unsold chore.

    leftovers:      (chore_id, effort_points) for every unsold chore
    member_order:   member ids in join order (used to break ties)
    effort_so_far:  effort each member already won at auction this week

    Rule: take the chores from biggest to smallest, and give each one to
    whoever has the lowest effort total so far. If two members are level,
    the one who joined first gets it.

    Returns {chore_id: member_id}.
    """
    if not member_order:
        raise ValueError("Cannot assign chores with no members")

    totals = {member: effort_so_far.get(member, 0) for member in member_order}
    join_position = {member: position for position, member in enumerate(member_order)}

    # Biggest effort first; equal efforts in chore id order, so the result never varies.
    by_size = sorted(leftovers, key=lambda chore: (-chore[1], chore[0]))

    assignments = {}
    for chore_id, effort in by_size:
        # min() compares the tuples left to right: lowest total first, then earliest joiner.
        member = min(member_order, key=lambda m: (totals[m], join_position[m]))
        assignments[chore_id] = member
        totals[member] += effort
    return assignments
