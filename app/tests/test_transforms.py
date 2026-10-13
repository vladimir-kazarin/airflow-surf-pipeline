import pandas as pd
import transforms

RAW = pd.DataFrame(
    {
        "spot": ["Bali", "Bali", "Hawaii", "Bali"],
        "ts": ["2026-10-11T06:00", "2026-10-12T06:00", "2026-10-12T07:00", "2026-10-12T07:00"],
        "wave_height": ["0.9", "1.2", "1.5", "0.3"],
        "wave_period": ["8.0", "11.0", "5.0", "4.0"],
        "wave_direction": ["90", "95", "100", "95"],
        "rating": ["FAIR", "GOOD", "POOR", "FLAT"],
    }
)
SPOT_INFO = [
    {"name": "Bali", "break": "Uluwatu", "timezone": "Asia/Makassar"},
    {"name": "Hawaii", "break": "Pipeline", "timezone": "Pacific/Honolulu"},
]


def test_prepare_types_columns_without_mutating_input():
    before = RAW.copy()

    prepared = transforms.prepare(RAW)

    assert prepared["wave_height"].dtype.kind == "f"
    assert prepared["surfable"].tolist() == [True, True, False, False]
    assert str(prepared["day"].iloc[0].date()) == "2026-10-11"
    pd.testing.assert_frame_equal(RAW, before)  # input untouched


def test_daily_summary_counts_surfable_hours_per_spot_and_day():
    daily = transforms.daily_summary(transforms.prepare(RAW))
    bali_12 = daily[(daily["spot"] == "Bali") & (daily["day"] == "2026-10-12")].iloc[0]

    assert bali_12["max_height"] == 1.2
    assert bali_12["surfable_hours"] == 1


def test_local_time_converts_from_utc():
    assert transforms.local_time("2026-10-12T06:00", "Asia/Makassar") == "14:00"  # UTC+8
    assert transforms.local_time("2026-10-12T06:00", "Pacific/Honolulu") == "20:00"  # UTC-10, previous day
    assert transforms.local_time("2026-10-12T06:00", None) == "06:00 UTC"


def test_spot_cards_merge_display_info_in_best_first_order():
    conditions = transforms.prepare(RAW)
    sessions = transforms.best_sessions_on(conditions, transforms.latest_day(conditions))

    cards = transforms.spot_cards(sessions, SPOT_INFO)

    assert [(c["spot"], c["break"], c["local_time"]) for c in cards] == [
        ("Bali", "Uluwatu", "14:00"),
        ("Hawaii", "Pipeline", "21:00"),
    ]


def test_spot_cards_tolerate_missing_spot_info():
    conditions = transforms.prepare(RAW)
    sessions = transforms.best_sessions_on(conditions, transforms.latest_day(conditions))
    assert transforms.spot_cards(sessions, [])[0]["local_time"].endswith("UTC")


def test_spot_series_limits_to_last_n_days_for_one_spot():
    daily = transforms.daily_summary(transforms.prepare(RAW))

    assert set(transforms.spot_series(daily, "Bali", 1)["day"].dt.day) == {12}
    assert len(transforms.spot_series(daily, "Bali", None)) == 2
    assert transforms.spot_series(daily, "Nowhere", 30).empty
