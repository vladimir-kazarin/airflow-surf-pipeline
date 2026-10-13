"""Surf Window dashboard: the public face of the Airflow pipeline in this repo."""

import sys
from pathlib import Path

import streamlit as st

# Reuse the pipeline's own pure-Python logic (rating, report, S3 layout).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dags"))

import charts  # noqa: E402
import transforms  # noqa: E402
from data import SOURCE_S3, Dataset, load_dataset  # noqa: E402

REPO_URL = "https://github.com/vladimir-kazarin/airflow-surf-pipeline"
CACHE_TTL_SECONDS = 60 * 60
RANGE_OPTIONS = {"30 days": 30, "60 days": 60, "90 days": 90, "All": None}
RECENT_RUNS_SHOWN = 15

st.set_page_config(page_title="Surf Window · Airflow pipeline", page_icon="🌊", layout="wide")


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Loading surf data…")
def get_dataset() -> Dataset:
    return load_dataset()


def theme_mode() -> str:
    return "dark" if (st.context.theme.get("type") == "dark") else "light"


def render_header(dataset: Dataset) -> None:
    meta = dataset.meta
    st.title("🌊 Surf Window")
    st.markdown(
        "Daily wave conditions for four East Coast surf spots, produced by an "
        f"**Apache Airflow 3** pipeline and published to **Amazon S3**. [Source on GitHub]({REPO_URL})"
    )
    source = "live from S3" if dataset.source == SOURCE_S3 else dataset.source
    st.caption(
        f"Data through **{meta['last_day']}** · {meta['days']} days · {meta['rows']:,} hourly rows · "
        f"published {meta['generated_at'].replace('T', ' ')[:16]} UTC by `{meta['source']}` · {source}"
    )
    if dataset.warning:
        st.warning(dataset.warning, icon="⚠️")


def render_latest(conditions, sessions: list[dict]) -> None:
    day = transforms.latest_day(conditions)
    st.subheader(f"Best sessions on {day:%A, %B %d}")
    st.markdown(f"**{transforms.verdict(sessions)}**")

    columns = st.columns(len(sessions))
    for column, session in zip(columns, sessions):
        column.metric(
            label=session["spot"],
            value=f"{session['wave_height']:.1f} m @ {session['wave_period']:.0f} s",
            border=True,
        )
        column.caption(f"{session['rating']} · best around {session['ts'][11:16]} UTC")


def render_history(conditions, mode: str, default_focus: str) -> None:
    daily = transforms.daily_summary(conditions)
    spots = sorted(daily["spot"].unique())

    # One filter row scopes every chart below it.
    left, right = st.columns([3, 2])
    focus = left.segmented_control("Spot", spots, default=default_focus, key="focus") or default_focus
    window = right.segmented_control("Range", list(RANGE_OPTIONS), default="90 days", key="range") or "90 days"
    shown = transforms.last_n_days(daily, RANGE_OPTIONS[window])

    st.markdown(f"#### Daily max wave height: {focus} vs. the other spots")
    st.altair_chart(charts.height_trend(shown, focus, mode), width="stretch")

    st.markdown("#### Surfable hours per day (FAIR or GOOD)")
    st.altair_chart(charts.surfable_heatmap(shown, mode), width="stretch")

    with st.expander("Show the data behind these charts"):
        st.dataframe(
            shown.sort_values(["day", "spot"], ascending=[False, True]),
            hide_index=True,
            width="stretch",
            column_config={"day": st.column_config.DateColumn("Day")},
        )


def render_how_its_built(dataset: Dataset, mode: str) -> None:
    st.markdown("### Architecture")
    st.graphviz_chart(charts.architecture(mode), width="stretch")
    st.markdown(
        """
- **Orchestration:** Apache Airflow 3. A daily ETL DAG with an HTTP sensor, one mapped task per surf spot,
  retries with exponential backoff, a data-quality gate and an idempotent load.
- **Data-aware scheduling:** the load emits an **Asset** event; the report and publish DAGs run because
  data changed, not because a clock ticked.
- **Storage:** one CSV per day in S3 (re-running a day overwrites exactly that object), plus a compacted
  serving file and `meta.json` that this app reads.
- **Runs daily on GitHub Actions:** the workflow assumes an AWS role via **OIDC** (no stored AWS keys),
  re-processes the last 3 days (idempotency makes missed days self-heal) and publishes.
- **Infrastructure as code:** bucket, OIDC role and this app's read-only user are defined in Terraform.
        """
    )
    st.markdown("### Recent pipeline runs")
    runs = dataset.runs.sort_values("published_at", ascending=False).head(RECENT_RUNS_SHOWN)
    st.dataframe(runs, hide_index=True, width="stretch")


def main() -> None:
    dataset = get_dataset()
    conditions = transforms.prepare(dataset.conditions)
    render_header(dataset)

    conditions_tab, built_tab = st.tabs(["Conditions", "How it's built"])
    sessions = transforms.best_sessions_on(conditions, transforms.latest_day(conditions))
    with conditions_tab:
        render_latest(conditions, sessions)
        st.divider()
        # Open on the spot with the best latest session: the most interesting line.
        render_history(conditions, theme_mode(), default_focus=sessions[0]["spot"])
    with built_tab:
        render_how_its_built(dataset, theme_mode())


main()
