"""The one place the app asks "what time is it?".

Code calls clock.now() instead of datetime.now(), so tests can replace it
and pretend time has passed (for the 30-second turn timer, invite expiry...).
"""

from datetime import datetime, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)
