"""Pure pandas transforms for the dashboard (no Streamlit, easy to test)."""

import pandas as pd
from surf_lib import report

NUMERIC_COLUMNS = ("wave_height", "wave_period", "wave_direction")


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


def verdict(sessions: list[dict]) -> str:
    if not report.has_surfable(sessions):
        return "Nothing worth paddling out for. Wax the board and wait for swell."
    top = sessions[0]
    return f"Go surf at {top['spot']} around {top['ts'][11:16]} UTC ({top['rating']})"


def last_n_days(frame: pd.DataFrame, days: int | None) -> pd.DataFrame:
    if days is None:
        return frame
    cutoff = frame["day"].max() - pd.Timedelta(days=days - 1)
    return frame.loc[frame["day"] >= cutoff]
