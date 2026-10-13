"""Surf Window dashboard: the public face of the Airflow pipeline in this repo."""

import sys
from pathlib import Path

import streamlit as st

# Reuse the pipeline's own pure-Python logic (rating, report, S3 layout).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dags"))

import charts  # noqa: E402
import transforms  # noqa: E402
from data import SOURCE_S3, Dataset, load_dataset  # noqa: E402
from surf_lib import report  # noqa: E402

REPO_URL = "https://github.com/vladimir-kazarin/airflow-surf-pipeline"
CACHE_TTL_SECONDS = 60 * 60
SPARKLINE_DAYS = 30
CARD_COLUMNS = 2
HISTORY_RANGES = {"30 days": 30, "90 days": 90, "All": None}
# Rating badges always show the word; color only reinforces it.
RATING_BADGE = {
    "GOOD": {"color": "green", "icon": None},
    "FAIR": {"color": "blue", "icon": None},
    "POOR": {"color": "gray", "icon": None},
    "FLAT": {"color": "gray", "icon": None},
    "HAZARDOUS": {"color": "red", "icon": ":material/warning:"},
}

st.set_page_config(page_title="Surf Window", page_icon="🌊", layout="centered")


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Loading surf data…")
def get_dataset() -> Dataset:
    return load_dataset()


def theme_mode() -> str:
    return "dark" if st.context.theme.get("type") == "dark" else "light"


def rating_badge(container, rating: str) -> None:
    style = RATING_BADGE.get(rating, RATING_BADGE["POOR"])
    container.badge(rating.title(), color=style["color"], icon=style["icon"])


@st.dialog("Wave history", width="large")
def show_history(card: dict, daily, mode: str) -> None:
    st.markdown(f"**{card['spot']}** · {card['break']}")
    window = st.segmented_control("Range", list(HISTORY_RANGES), default="90 days", label_visibility="collapsed")
    series = transforms.spot_series(daily, card["spot"], HISTORY_RANGES[window or "90 days"])
    st.altair_chart(charts.history(series, mode), width="stretch")
    if st.toggle("Show data"):
        st.dataframe(
            series.sort_values("day", ascending=False).drop(columns="spot"),
            hide_index=True,
            width="stretch",
            column_config={"day": st.column_config.DateColumn("Day")},
        )


def render_card(card: dict, daily, mode: str) -> None:
    with st.container(border=True):
        header = st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="top")
        header.markdown(f"**{card['spot']}**  \n:gray[{card['break']}]")
        rating_badge(header, card["rating"])

        st.markdown(f"### {card['wave_height']:.1f} m :gray[· {card['wave_period']:.0f} s]")
        st.caption(f"Best around {card['local_time']} local")

        recent = transforms.spot_series(daily, card["spot"], SPARKLINE_DAYS)
        st.altair_chart(charts.sparkline(recent, mode), width="stretch")
        if st.button("History", key=f"history-{card['spot']}", type="tertiary", icon=":material/show_chart:"):
            show_history(card, daily, mode)


def render_footer(dataset: Dataset, mode: str) -> None:
    meta = dataset.meta
    source = "live from S3" if dataset.source == SOURCE_S3 else dataset.source
    st.divider()
    st.caption(
        f"Updated {meta['generated_at'][:10]} by `{meta['source']}` · {source} · "
        f"{meta['days']} days of hourly data · [Source on GitHub]({REPO_URL})"
    )
    with st.expander("How this works"):
        st.graphviz_chart(charts.architecture(mode), width="stretch")
        st.markdown(
            "An **Apache Airflow 3** DAG fetches hourly wave data every day, rates each hour, "
            "validates it and loads it. Its **Asset** event triggers a second DAG that publishes "
            "one file per day to **Amazon S3**. In production it runs on **GitHub Actions** with "
            "OIDC (no stored keys); infrastructure is **Terraform**. Ratings use wave height and "
            "period: *Good* is 0.8–2.5 m with a 10 s+ period."
        )


def main() -> None:
    dataset = get_dataset()
    conditions = transforms.prepare(dataset.conditions)
    daily = transforms.daily_summary(conditions)
    day = transforms.latest_day(conditions)
    cards = transforms.spot_cards(
        transforms.best_sessions_on(conditions, day), dataset.meta.get("spot_info", [])
    )
    mode = theme_mode()

    st.title("🌊 Surf Window")
    st.caption(f"Surf conditions around the world · {day:%A, %B %-d}")
    if dataset.warning:
        st.warning(dataset.warning, icon=":material/cloud_off:")

    best = cards[0]
    if report.has_surfable(cards):
        st.markdown(f"Best bet: **{best['spot']}**, {best['rating'].lower()} around {best['local_time']} local.")
    else:
        st.markdown(f"No surfable waves anywhere. **{best['spot']}** is the least bad.")

    for start in range(0, len(cards), CARD_COLUMNS):
        for column, card in zip(st.columns(CARD_COLUMNS), cards[start : start + CARD_COLUMNS]):
            with column:
                render_card(card, daily, mode)

    render_footer(dataset, mode)


main()
