"""Surf rating rules (ported from ~/dev/surf_window)."""

from enum import Enum

HAZARDOUS_HEIGHT_M = 3.0
FLAT_HEIGHT_M = 0.4
GOOD_MIN_PERIOD_S = 10.0
FAIR_MIN_PERIOD_S = 7.0


class Rating(str, Enum):
    FLAT = "FLAT"
    POOR = "POOR"
    FAIR = "FAIR"
    GOOD = "GOOD"
    HAZARDOUS = "HAZARDOUS"


# Higher score = better session. Used to pick the best hour of the day.
RATING_SCORE = {
    Rating.HAZARDOUS: 0,
    Rating.FLAT: 0,
    Rating.POOR: 1,
    Rating.FAIR: 2,
    Rating.GOOD: 3,
}


def rate(wave_height: float | None, wave_period: float | None) -> Rating:
    """Rate conditions from wave height (m) and period (s)."""
    if wave_height is None or wave_period is None:
        return Rating.FLAT
    if wave_height >= HAZARDOUS_HEIGHT_M:
        return Rating.HAZARDOUS
    if wave_height < FLAT_HEIGHT_M:
        return Rating.FLAT
    if wave_period >= GOOD_MIN_PERIOD_S and 0.8 <= wave_height < 2.5:
        return Rating.GOOD
    if wave_period >= FAIR_MIN_PERIOD_S and 0.5 <= wave_height < 2.0:
        return Rating.FAIR
    return Rating.POOR
