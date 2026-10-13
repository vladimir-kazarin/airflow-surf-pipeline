"""Altair specs. One series per chart, so a single accent hue and no legend (the title
names the series). Colors follow the dataviz reference palette, with dark-mode steps."""

import altair as alt
import pandas as pd

PALETTE = {
    "light": {"accent": "#2a78d6", "fill": "#cde2fb", "surface": "#fcfcfb", "ink": "#0b0b0b", "muted": "#898781"},
    "dark": {"accent": "#3987e5", "fill": "#184f95", "surface": "#1a1a19", "ink": "#f0efec", "muted": "#898781"},
}
SPARKLINE_HEIGHT = 56
HISTORY_HEIGHT = 280
DAY_TOOLTIP = alt.Tooltip("day:T", title="Day", format="%a %b %d")
HEIGHT_TOOLTIP = alt.Tooltip("max_height:Q", title="Max height (m)")


def sparkline(series: pd.DataFrame, mode: str) -> alt.Chart:
    """Tiny 'shape of the last month' chart for a card: no axes, hover for values."""
    colors = PALETTE[mode]
    hidden = alt.Axis(labels=False, ticks=False, domain=False, grid=False, title=None)
    base = alt.Chart(series).encode(
        x=alt.X("day:T", axis=hidden),
        y=alt.Y("max_height:Q", axis=hidden, scale=alt.Scale(zero=True)),
    )
    area = base.mark_area(color=colors["fill"], opacity=0.6)
    line = base.mark_line(color=colors["accent"], strokeWidth=2)
    hover = alt.selection_point(fields=["day"], nearest=True, on="pointerover", empty=False)
    points = base.mark_point(size=60, filled=True, color=colors["accent"]).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[DAY_TOOLTIP, HEIGHT_TOOLTIP],
    ).add_params(hover)
    return (
        alt.layer(area, line, points)
        .properties(height=SPARKLINE_HEIGHT)
        .configure_view(strokeWidth=0)
    )


def history(series: pd.DataFrame, mode: str) -> alt.Chart:
    """Daily max wave height for one spot, with a crosshair tooltip."""
    colors = PALETTE[mode]
    base = alt.Chart(series).encode(
        x=alt.X("day:T", title=None, axis=alt.Axis(format="%b %d", grid=False)),
        y=alt.Y("max_height:Q", title="Max wave height (m)", scale=alt.Scale(zero=True)),
    )
    area = base.mark_area(color=colors["fill"], opacity=0.5)
    line = base.mark_line(color=colors["accent"], strokeWidth=2)
    hover = alt.selection_point(fields=["day"], nearest=True, on="pointerover", empty=False)
    rule = base.mark_rule(color=colors["muted"]).encode(
        opacity=alt.condition(hover, alt.value(0.6), alt.value(0)),
        tooltip=[
            DAY_TOOLTIP,
            HEIGHT_TOOLTIP,
            alt.Tooltip("mean_period:Q", title="Mean period (s)"),
            alt.Tooltip("surfable_hours:Q", title="Surfable hours"),
        ],
    ).add_params(hover)
    point = base.mark_point(size=70, filled=True, color=colors["accent"], stroke=colors["surface"], strokeWidth=2).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0))
    )
    return alt.layer(area, line, rule, point).properties(height=HISTORY_HEIGHT).configure_view(strokeWidth=0)


def architecture(mode: str) -> str:
    """Graphviz DOT for the pipeline. Graphviz ignores the page theme, so ink is set per mode."""
    colors = PALETTE[mode]
    ink, muted = colors["ink"], colors["muted"]
    return f"""
digraph {{
  rankdir=LR; bgcolor="transparent";
  node [shape=box, style="rounded", fontname="sans-serif", fontsize=11, color="{muted}", fontcolor="{ink}"];
  edge [fontname="sans-serif", fontsize=9, color="{muted}", fontcolor="{muted}"];
  api [label="Open-Meteo\\nMarine API"];
  etl [label="Airflow ETL\\nfetch → rate → validate → load", color="{colors['accent']}"];
  pub [label="Airflow publish\\n(asset-triggered)"];
  s3  [label="Amazon S3"];
  app [label="This page"];
  api -> etl; etl -> pub [label="Asset event", style=dashed]; pub -> s3; s3 -> app;
}}
"""
