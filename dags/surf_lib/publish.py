"""S3 layout and (de)serialization for the published dataset. No AWS calls here.

    s3://<bucket>/conditions/day=2026-10-12.csv   one file per day (the "lake")
    s3://<bucket>/serving/surf_conditions.csv     all days compacted (what the app reads)
    s3://<bucket>/serving/meta.json               freshness + provenance
    s3://<bucket>/serving/pipeline_runs.csv       one row per publish

Writing one object per day makes publishing idempotent: re-processing a day
overwrites exactly that day's object and nothing else.
"""

import csv
import io
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence

from surf_lib.storage import COLUMNS

CONDITIONS_PREFIX = "conditions/"
SERVING_KEY = "serving/surf_conditions.csv"
META_KEY = "serving/meta.json"
RUNS_KEY = "serving/pipeline_runs.csv"
RUN_COLUMNS = ("published_at", "source", "run_id", "days_published", "rows_total", "last_day")
MAX_RUN_HISTORY = 500


def partition_key(day: str) -> str:
    return f"{CONDITIONS_PREFIX}day={day}.csv"


def group_by_day(rows: Iterable[Sequence]) -> dict[str, list[Sequence]]:
    """rows are in storage.COLUMNS order; ts ("2026-10-12T06:00") carries the day."""
    by_day: dict[str, list[Sequence]] = defaultdict(list)
    for row in rows:
        by_day[row[COLUMNS.index("ts")][:10]].append(row)
    return dict(by_day)


def to_csv(rows: Iterable[Sequence], header: Sequence[str] = COLUMNS) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def parse_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def build_meta(rows: list[dict], generated_at: str, source: str, run_id: str) -> dict:
    days = sorted({r["ts"][:10] for r in rows})
    return {
        "generated_at": generated_at,
        "source": source,
        "run_id": run_id,
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "days": len(days),
        "spots": sorted({r["spot"] for r in rows}),
        "rows": len(rows),
    }


def append_run(existing_csv: str | None, entry: dict) -> str:
    """Return the runs log with `entry` appended, keeping the newest MAX_RUN_HISTORY rows."""
    previous = parse_csv(existing_csv) if existing_csv else []
    runs = [*previous, entry][-MAX_RUN_HISTORY:]
    return to_csv(([r.get(col, "") for col in RUN_COLUMNS] for r in runs), RUN_COLUMNS)


def to_json(data: dict) -> str:
    return json.dumps(data, indent=2)
