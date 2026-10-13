import pytest
from surf_lib.marine import to_rows
from surf_lib.rating import Rating, rate


@pytest.mark.parametrize(
    ("height", "period", "expected"),
    [
        (3.2, 12.0, Rating.HAZARDOUS),
        (0.3, 12.0, Rating.FLAT),
        (1.2, 11.0, Rating.GOOD),
        (0.9, 8.0, Rating.FAIR),
        (1.5, 5.0, Rating.POOR),
        (None, 8.0, Rating.FLAT),
    ],
)
def test_rate(height, period, expected):
    assert rate(height, period) is expected


def test_to_rows_flattens_hourly_columns():
    payload = {
        "hourly": {
            "time": ["2026-10-10T00:00", "2026-10-10T01:00"],
            "wave_height": [1.2, 0.2],
            "wave_period": [11.0, 4.0],
            "wave_direction": [90, 95],
        }
    }

    rows = to_rows("Montauk", payload)

    assert [r["rating"] for r in rows] == ["GOOD", "FLAT"]
    assert rows[0] == {
        "spot": "Montauk",
        "ts": "2026-10-10T00:00",
        "wave_height": 1.2,
        "wave_period": 11.0,
        "wave_direction": 90,
        "rating": "GOOD",
    }


def test_to_rows_rejects_unexpected_payload():
    with pytest.raises(ValueError):
        to_rows("Montauk", {"error": True, "reason": "bad request"})
