import pandas as pd
import transforms

RAW = pd.DataFrame(
    {
        "spot": ["Montauk", "Montauk", "Rockaway", "Montauk"],
        "ts": ["2026-10-11T06:00", "2026-10-12T06:00", "2026-10-12T07:00", "2026-10-12T07:00"],
        "wave_height": ["0.9", "1.2", "1.5", "0.3"],
        "wave_period": ["8.0", "11.0", "5.0", "4.0"],
        "wave_direction": ["90", "95", "100", "95"],
        "rating": ["FAIR", "GOOD", "POOR", "FLAT"],
    }
)


def test_prepare_types_columns_without_mutating_input():
    before = RAW.copy()

    prepared = transforms.prepare(RAW)

    assert prepared["wave_height"].dtype.kind == "f"
    assert prepared["surfable"].tolist() == [True, True, False, False]
    assert str(prepared["day"].iloc[0].date()) == "2026-10-11"
    pd.testing.assert_frame_equal(RAW, before)  # input untouched


def test_daily_summary_counts_surfable_hours_per_spot_and_day():
    daily = transforms.daily_summary(transforms.prepare(RAW))
    montauk_12 = daily[(daily["spot"] == "Montauk") & (daily["day"] == "2026-10-12")].iloc[0]

    assert montauk_12["max_height"] == 1.2
    assert montauk_12["surfable_hours"] == 1


def test_best_sessions_and_verdict_for_latest_day():
    conditions = transforms.prepare(RAW)
    sessions = transforms.best_sessions_on(conditions, transforms.latest_day(conditions))

    assert [s["spot"] for s in sessions] == ["Montauk", "Rockaway"]
    assert transforms.verdict(sessions).startswith("Go surf at Montauk around 06:00")


def test_verdict_when_nothing_is_surfable():
    assert "Nothing worth paddling out" in transforms.verdict([{"rating": "POOR"}])


def test_last_n_days():
    daily = transforms.daily_summary(transforms.prepare(RAW))
    assert set(transforms.last_n_days(daily, 1)["day"].dt.day) == {12}
    assert len(transforms.last_n_days(daily, None)) == len(daily)
