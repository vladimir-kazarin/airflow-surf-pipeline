"""SQL used by the DAGs. The DAGs execute it through SqliteHook (conn_id="surf_db")."""

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS surf_conditions (
    spot           TEXT NOT NULL,
    ts             TEXT NOT NULL,   -- ISO-8601 hour, UTC
    wave_height    REAL,
    wave_period    REAL,
    wave_direction REAL,
    rating         TEXT NOT NULL,
    PRIMARY KEY (spot, ts)
)
"""

# Primary key + REPLACE makes loads idempotent: re-running a day overwrites
# that day's rows instead of duplicating them. Idempotency is what makes
# retries and backfills safe.
COLUMNS = ("spot", "ts", "wave_height", "wave_period", "wave_direction", "rating")

LATEST_DAY = "SELECT MAX(substr(ts, 1, 10)) FROM surf_conditions"

DAY_ROWS = """
SELECT spot, ts, wave_height, wave_period, rating
FROM surf_conditions
WHERE substr(ts, 1, 10) = ?
ORDER BY spot, ts
"""
