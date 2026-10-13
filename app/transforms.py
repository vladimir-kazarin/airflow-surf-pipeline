"""Pure pandas transforms for the dashboard (no Streamlit, easy to test)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from surf_lib import report

NUMERIC_COLUMNS = ("wave_height", "wave_period", "wave_direction")
UTC = ZoneInfo("UTC")


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    """Type the raw CSV columns and add `day` / `surfable`. Returns a new frame."""
    typed = raw.assign(
        ts=pd.to_datetime(raw["ts"]),
        **{col: pd.to_numeric(raw[col], errors="coerce") for col in NUMERIC_COLUMNS},
    )
    return typed.assign(
        day=typed["ts"].dt.normalize(),
        surfable=typed["rating"].isin(report.SURFABLE),
    )


def daily_summary(conditions: pd.DataFrame) -> pd.DataFrame:
    """One row per (day, spot): max height, mean period, surfable hours."""
    return (
        conditions.groupby(["day", "spot"], as_index=False)
        .agg(
            max_height=("wave_height", "max"),
            mean_period=("wave_period", "mean"),
            surfable_hours=("surfable", "sum"),
        )
        .round({"max_height": 2, "mean_period": 1})
    )


def latest_day(conditions: pd.DataFrame) -> pd.Timestamp:
    return conditions["day"].max()


def best_sessions_on(conditions: pd.DataFrame, day: pd.Timestamp) -> list[dict]:
    """Best hour per spot on `day`, best first (same logic as the Airflow report DAG)."""
    rows = conditions.loc[conditions["day"] == day]
    records = zip(
        rows["spot"],
        rows["ts"].dt.strftime("%Y-%m-%dT%H:%M"),
        rows["wave_height"],
        rows["wave_period"],
        rows["rating"],
    )
    return report.best_sessions(list(records))


def local_time(ts_utc: str, timezone: str | None) -> str:
    """'2026-10-12T06:00' (UTC) -> '14:00' in the spot's timezone ('06:00 UTC' if unknown)."""
    moment = datetime.fromisoformat(ts_utc).replace(tzinfo=UTC)
    if not timezone:
        return f"{moment:%H:%M} UTC"
    return f"{moment.astimezone(ZoneInfo(timezone)):%H:%M}"


def spot_cards(sessions: list[dict], spot_info: list[dict]) -> list[dict]:
    """Merge each spot's best session with its display info, keeping best-first order."""
    info_by_name = {s["name"]: s for s in spot_info}
    cards = []
    for session in sessions:
        info = info_by_name.get(session["spot"], {})
        cards.append(
            {
                **session,
                "break": info.get("break") or "",
                "local_time": local_time(session["ts"], info.get("timezone")),
            }
        )
    return cards


def spot_series(daily: pd.DataFrame, spot: str, days: int | None) -> pd.DataFrame:
    """One spot's daily rows, limited to its last `days` days (None = all)."""
    rows = daily.loc[daily["spot"] == spot]
    if days is None or rows.empty:
        return rows
    cutoff = rows["day"].max() - pd.Timedelta(days=days - 1)
    return rows.loc[rows["day"] >= cutoff]
