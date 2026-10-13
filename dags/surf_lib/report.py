"""Pick each spot's best hour and render a Markdown surf report."""

from surf_lib.rating import RATING_SCORE, Rating

SURFABLE = {Rating.GOOD.value, Rating.FAIR.value}


def best_sessions(rows: list[tuple]) -> list[dict]:
    """rows: (spot, ts, wave_height, wave_period, rating). Returns the best hour per spot."""
    best: dict[str, dict] = {}
    for spot, ts, height, period, rating in rows:
        candidate = {
            "spot": spot,
            "ts": ts,
            "wave_height": height,
            "wave_period": period,
            "rating": rating,
        }
        current = best.get(spot)
        if current is None or _score(candidate) > _score(current):
            best[spot] = candidate
    return sorted(best.values(), key=_score, reverse=True)


def _score(session: dict) -> tuple:
    # Rating first, then bigger waves as tiebreaker.
    return (RATING_SCORE[Rating(session["rating"])], session["wave_height"] or 0)


def has_surfable(sessions: list[dict]) -> bool:
    return any(s["rating"] in SURFABLE for s in sessions)


def render_markdown(day: str, sessions: list[dict], verdict: str) -> str:
    lines = [
        f"# Surf report — {day}",
        "",
        f"**Verdict:** {verdict}",
        "",
        "| Spot | Best hour (UTC) | Height (m) | Period (s) | Rating |",
        "|---|---|---|---|---|",
    ]
    for s in sessions:
        hour = s["ts"][11:16]
        lines.append(
            f"| {s['spot']} | {hour} | {s['wave_height']} | {s['wave_period']} | {s['rating']} |"
        )
    return "\n".join(lines) + "\n"
