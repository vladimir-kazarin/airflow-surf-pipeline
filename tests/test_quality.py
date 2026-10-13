from surf_lib.quality import EXPECTED_HOURS_PER_DAY, find_problems


def _day(height=1.0, hours=EXPECTED_HOURS_PER_DAY):
    return [{"spot": "Montauk", "wave_height": height} for _ in range(hours)]


def test_clean_day_has_no_problems():
    assert find_problems("Montauk", _day()) == []


def test_missing_hours_are_reported():
    assert "got 20" in find_problems("Montauk", _day(hours=20))[0]


def test_mostly_missing_heights_are_reported():
    problems = find_problems("Montauk", _day(height=None))
    assert any("no wave height" in p for p in problems)


def test_implausible_heights_are_reported():
    problems = find_problems("Montauk", _day(height=42.0))
    assert any("implausible" in p for p in problems)


def test_empty_day_reports_only_the_count():
    assert len(find_problems("Montauk", [])) == 1
