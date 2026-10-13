from surf_lib.report import best_sessions, has_surfable, render_markdown

ROWS = [
    ("Montauk", "2026-10-10T06:00", 0.9, 8.0, "FAIR"),
    ("Montauk", "2026-10-10T07:00", 1.2, 11.0, "GOOD"),
    ("Rockaway", "2026-10-10T06:00", 1.5, 5.0, "POOR"),
    ("Rockaway", "2026-10-10T07:00", 1.8, 5.0, "POOR"),
]


def test_best_sessions_picks_best_hour_per_spot_sorted_best_first():
    sessions = best_sessions(ROWS)

    assert [(s["spot"], s["ts"]) for s in sessions] == [
        ("Montauk", "2026-10-10T07:00"),
        ("Rockaway", "2026-10-10T07:00"),  # same rating -> bigger wave wins
    ]


def test_has_surfable():
    assert has_surfable(best_sessions(ROWS))
    assert not has_surfable(best_sessions(ROWS[2:]))


def test_render_markdown_has_one_row_per_spot():
    md = render_markdown("2026-10-10", best_sessions(ROWS), "Go surf")

    assert "# Surf report — 2026-10-10" in md
    assert "| Montauk | 07:00 | 1.2 | 11.0 | GOOD |" in md
    assert md.count("\n| ") == 3  # header + 2 spots
