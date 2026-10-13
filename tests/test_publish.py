import json

from surf_lib import publish

ROWS = [
    ("Montauk", "2026-10-11T00:00", 1.2, 11.0, 90.0, "GOOD"),
    ("Montauk", "2026-10-12T00:00", 0.3, 4.0, 95.0, "FLAT"),
    ("Rockaway", "2026-10-12T00:00", 0.9, 8.0, 100.0, "FAIR"),
]


def test_partition_key_is_one_object_per_day():
    assert publish.partition_key("2026-10-12") == "conditions/day=2026-10-12.csv"


def test_group_by_day():
    by_day = publish.group_by_day(ROWS)
    assert sorted(by_day) == ["2026-10-11", "2026-10-12"]
    assert len(by_day["2026-10-12"]) == 2


def test_csv_round_trip():
    parsed = publish.parse_csv(publish.to_csv(ROWS))
    assert parsed[0] == {
        "spot": "Montauk",
        "ts": "2026-10-11T00:00",
        "wave_height": "1.2",
        "wave_period": "11.0",
        "wave_direction": "90.0",
        "rating": "GOOD",
    }


def test_build_meta():
    rows = publish.parse_csv(publish.to_csv(ROWS))
    meta = publish.build_meta(rows, generated_at="2026-10-13T01:30:00+00:00", source="ci", run_id="r1")
    assert meta["first_day"] == "2026-10-11"
    assert meta["last_day"] == "2026-10-12"
    assert meta["spots"] == ["Montauk", "Rockaway"]
    assert meta["rows"] == 3
    assert json.loads(publish.to_json(meta)) == meta


def test_only_spots_drops_spots_removed_from_config():
    rows = publish.parse_csv(publish.to_csv(ROWS))
    kept = publish.only_spots(rows, ["Rockaway"])
    assert [r["spot"] for r in kept] == ["Rockaway"]


def test_build_meta_carries_spot_display_info_only():
    spot = {"name": "Bali", "break": "Uluwatu", "timezone": "Asia/Makassar",
            "latitude": -8.8, "longitude": 115.1, "internal": "dropped"}
    meta = publish.build_meta([], "now", "ci", "r1", spot_info=[spot])
    assert meta["spot_info"] == [
        {"name": "Bali", "break": "Uluwatu", "timezone": "Asia/Makassar",
         "latitude": -8.8, "longitude": 115.1}
    ]


def test_build_meta_handles_no_rows():
    assert publish.build_meta([], "now", "ci", "r1")["last_day"] is None


def test_append_run_keeps_history_and_caps_it():
    log = None
    for i in range(publish.MAX_RUN_HISTORY + 5):
        log = publish.append_run(log, {"run_id": f"r{i}", "rows_total": i})

    runs = publish.parse_csv(log)
    assert len(runs) == publish.MAX_RUN_HISTORY
    assert runs[-1]["run_id"] == f"r{publish.MAX_RUN_HISTORY + 4}"
    assert list(runs[0]) == list(publish.RUN_COLUMNS)
