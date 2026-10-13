"""Altair chart specs. Colors follow the dataviz reference palette:
- trend: *emphasis* form (selected spot in the accent hue, other spots muted gray)
- heatmap: one-hue sequential ramp, with its own dark-mode steps
"""

import altair as alt
import pandas as pd

PALETTE = {
    "light": {
        "accent": "#2a78d6",
        "context": "#898781",
        "surface": "#fcfcfb",
        "ink": "#0b0b0b",
        "sequential": ["#cde2fb", "#0d366b"],  # near-zero recedes toward the light surface
    },
    "dark": {
        "accent": "#3987e5",
        "context": "#898781",
        "surface": "#1a1a19",
        "ink": "#f0efec",
        "sequential": ["#104281", "#cde2fb"],  # near-zero recedes toward the dark surface
    },
}
CHART_HEIGHT = 300
HEATMAP_ROW_PX = 34
HOURS_PER_DAY = 24
DAY_MS = 24 * 60 * 60 * 1000


def height_trend(daily: pd.DataFrame, focus: str, mode: str) -> alt.Chart:
    """Daily max wave height: `focus` spot emphasized, the rest as gray context."""
    colors = PALETTE[mode]
    spots = sorted(daily["spot"].unique())
    base = alt.Chart(daily).encode(
        x=alt.X("day:T", title=None, axis=alt.Axis(format="%b %d", grid=False)),
        y=alt.Y("max_height:Q", title="Max wave height (m)"),
    )
    is_focus = alt.datum.spot == focus

    context = (
        base.transform_filter(~is_focus)
        .mark_line(strokeWidth=1.5, opacity=0.45, color=colors["context"])
        .encode(detail="spot:N")
    )
    focus_line = base.transform_filter(is_focus).mark_line(strokeWidth=2, color=colors["accent"])
    end_label = (
        base.transform_filter(is_focus)
        .transform_window(rank="rank()", sort=[alt.SortField("day", order="descending")])
        .transform_filter("datum.rank == 1")
        .mark_text(align="left", dx=8, fontWeight="bold", color=colors["ink"])  # ink, not series color
        .encode(text="spot:N")
    )

    # Crosshair: hovering anywhere snaps to the nearest day and shows every spot.
    hover = alt.selection_point(fields=["day"], nearest=True, on="pointerover", empty=False)
    crosshair = (
        alt.Chart(daily)
        .transform_pivot("spot", value="max_height", groupby=["day"])
        .mark_rule(color=colors["context"])
        .encode(
            x="day:T",
            opacity=alt.condition(hover, alt.value(0.6), alt.value(0)),
            tooltip=[alt.Tooltip("day:T", title="Day", format="%a %b %d")]
            + [alt.Tooltip(f"{spot}:Q", title=f"{spot} (m)") for spot in spots],
        )
        .add_params(hover)
    )
    focus_point = (
        base.transform_filter(is_focus)
        .mark_point(size=70, filled=True, color=colors["accent"], stroke=colors["surface"], strokeWidth=2)
        .encode(opacity=alt.condition(hover, alt.value(1), alt.value(0)))
    )

    return (
        alt.layer(context, focus_line, crosshair, focus_point, end_label)
        .properties(height=CHART_HEIGHT)
        .configure_view(strokeWidth=0)
    )


def architecture(mode: str) -> str:
    """Graphviz DOT for the pipeline. Graphviz ignores the page theme, so ink is set per mode."""
    colors = PALETTE[mode]
    ink, muted = colors["ink"], colors["context"]
    return f"""
digraph {{
  rankdir=LR; bgcolor="transparent";
  node [shape=box, style="rounded", fontname="sans-serif", fontsize=11, color="{muted}", fontcolor="{ink}"];
  edge [fontname="sans-serif", fontsize=9, color="{muted}", fontcolor="{muted}"];
  api [label="Open-Meteo\\nMarine API"];
  etl [label="02_surf_etl\\nsensor → fetch[×spots] → transform → validate → load", color="{colors['accent']}"];
  db  [label="SQLite\\n(working store)"];
  pub [label="04_publish_snapshot\\nS3Hook"];
  rep [label="03_surf_report\\nbranch → markdown"];
  s3  [label="S3\\nconditions/day=*.csv\\nserving/*"];
  app [label="Streamlit\\n(this page)"];
  api -> etl [label="HTTP"]; etl -> db;
  etl -> pub [label="Asset event", style=dashed]; etl -> rep [label="Asset event", style=dashed];
  db -> pub; pub -> s3; s3 -> app [label="read-only IAM"];
}}
"""


def surfable_heatmap(daily: pd.DataFrame, mode: str) -> alt.Chart:
    """Spot x day grid; darker = more surfable (FAIR/GOOD) hours that day."""
    colors = PALETTE[mode]
    return (
        alt.Chart(daily)
        .transform_calculate(day_end=f"datum.day + {DAY_MS}")
        .mark_rect(stroke=colors["surface"], strokeWidth=1, cornerRadius=2)
        .encode(
            x=alt.X("day:T", title=None, axis=alt.Axis(format="%b %d", grid=False)),
            x2="day_end:T",
            y=alt.Y("spot:N", title=None, sort="ascending"),
            color=alt.Color(
                "surfable_hours:Q",
                scale=alt.Scale(domain=[0, HOURS_PER_DAY], range=colors["sequential"]),
                legend=alt.Legend(title="Surfable hours", orient="top", gradientLength=180),
            ),
            tooltip=[
                alt.Tooltip("day:T", title="Day", format="%a %b %d"),
                alt.Tooltip("spot:N", title="Spot"),
                alt.Tooltip("surfable_hours:Q", title="Surfable hours"),
                alt.Tooltip("max_height:Q", title="Max height (m)"),
                alt.Tooltip("mean_period:Q", title="Mean period (s)"),
            ],
        )
        .properties(height=alt.Step(HEATMAP_ROW_PX))  # fixed row height: every spot label fits
        .configure_view(strokeWidth=0)
    )
