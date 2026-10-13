"""Turn an Open-Meteo marine API response into flat, rated rows."""

from surf_lib.rating import rate

HOURLY_FIELDS = ("wave_height", "wave_period", "wave_direction")
MARINE_ENDPOINT = "v1/marine"


def build_params(spot: dict, day: str) -> dict:
    """Query params asking for one full UTC day of hourly data for one spot."""
    return {
        "latitude": spot["latitude"],
        "longitude": spot["longitude"],
        "hourly": ",".join(HOURLY_FIELDS),
        "start_date": day,
        "end_date": day,
        "timezone": "UTC",
    }


def to_rows(spot_name: str, payload: dict) -> list[dict]:
    """Flatten the column-oriented `hourly` block into one dict per hour."""
    hourly = payload.get("hourly")
    if not hourly or "time" not in hourly:
        raise ValueError(f"Unexpected marine API payload for {spot_name}: {payload!r:.200}")

    rows = []
    for i, ts in enumerate(hourly["time"]):
        height = hourly["wave_height"][i]
        period = hourly["wave_period"][i]
        rows.append(
            {
                "spot": spot_name,
                "ts": ts,
                "wave_height": height,
                "wave_period": period,
                "wave_direction": hourly["wave_direction"][i],
                "rating": rate(height, period).value,
            }
        )
    return rows
