"""Data-quality rules applied before anything is loaded.

A pipeline that silently loads garbage is worse than one that fails loudly,
so `validate` in 02_surf_etl fails the run if any of these trip.
"""

EXPECTED_HOURS_PER_DAY = 24
MAX_PLAUSIBLE_HEIGHT_M = 20.0
MAX_MISSING_SHARE = 0.25


def find_problems(spot: str, rows: list[dict]) -> list[str]:
    """Return human-readable problems with one spot's day of hourly rows (empty = OK)."""
    problems = []
    if len(rows) != EXPECTED_HOURS_PER_DAY:
        problems.append(f"{spot}: expected {EXPECTED_HOURS_PER_DAY} hourly rows, got {len(rows)}")
    if not rows:
        return problems

    heights = [r["wave_height"] for r in rows]
    missing = sum(h is None for h in heights)
    if missing / len(rows) > MAX_MISSING_SHARE:
        problems.append(f"{spot}: {missing}/{len(rows)} hours have no wave height")

    implausible = [h for h in heights if h is not None and not 0 <= h <= MAX_PLAUSIBLE_HEIGHT_M]
    if implausible:
        problems.append(f"{spot}: implausible wave heights {implausible[:3]}")
    return problems
