"""
### Lesson 2: a real daily ETL

Every day, fetch yesterday's hourly wave data for each spot, rate each hour,
and load it into SQLite.

Concepts:
- **Schedule & data interval**: we use `CronDataIntervalTimetable`, so the
  run for interval [Oct 12, Oct 13) has logical date Oct 12, starts *after*
  Oct 13 00:00 (once the day is complete), and processes Oct 12. The day comes
  from `logical_date`, never from "now", so re-runs give the same result.
  (Airflow 3's default for cron strings is `CronTriggerTimetable`: logical
  date = the moment it fires, zero-length interval. Fine for "do X at 6am"
  jobs, wrong for "process yesterday's data" jobs like this one.)
- **Backfill**: because of that, you can process any past day range:
  `airflow backfill create --dag-id 02_surf_etl --from-date 2026-10-01 --to-date 2026-10-07`
- **Sensor**: `api_is_up` waits until the API answers before doing work.
- **Connections**: hooks look up `open_meteo_marine` / `surf_db` by id.
- **Variables**: the list of spots comes from the `surf_spots` Variable.
- **Dynamic task mapping**: `.partial(...).expand(...)` creates one task
  instance per spot at runtime. Add a spot, get another task, no code change.
- **Retries**: `default_args` apply retries/backoff/timeouts to every task.
- **Data-quality gate**: `validate` fails the run before bad data is loaded.
- **Idempotent load**: `REPLACE INTO` on a primary key, so re-runs are safe.
- **Asset outlet**: `load` emits a `surf_conditions` event (with the processed
  day in its `extra`) that triggers DAGs 03 and 04.
"""

from datetime import timedelta

import pendulum
from airflow.providers.http.hooks.http import HttpHook
from airflow.providers.http.sensors.http import HttpSensor
from airflow.providers.sqlite.hooks.sqlite import SqliteHook
from airflow.sdk import Variable, dag, get_current_context, task
from airflow.sdk.exceptions import AirflowFailException
from airflow.timetables.interval import CronDataIntervalTimetable

from surf_lib import marine, quality, storage
from surf_lib.assets import SURF_CONDITIONS

MARINE_CONN_ID = "open_meteo_marine"
DB_CONN_ID = "surf_db"
MAX_PARALLEL_API_CALLS = 2  # be polite to a free API

default_args = {
    "owner": "vladi",
    "retries": 3,
    "retry_delay": timedelta(seconds=20),
    "retry_exponential_backoff": True,  # 20s, 40s, 80s...
    "execution_timeout": timedelta(minutes=5),
}


@dag(
    dag_id="02_surf_etl",
    # Daily at 00:00 UTC, processing the day that just ended (see docstring).
    schedule=CronDataIntervalTimetable("0 0 * * *", timezone="UTC"),
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    # catchup=False: when you unpause, Airflow does NOT create runs for every
    # missed day since start_date. Use an explicit backfill for history instead.
    catchup=False,
    max_active_runs=3,
    default_args=default_args,
    tags=["surf", "lesson-2"],
    doc_md=__doc__,
)
def surf_etl():
    # --- Sensor ------------------------------------------------------------
    # mode="reschedule" frees the worker slot between pokes (vs. "poke",
    # which sleeps while holding the slot).
    api_is_up = HttpSensor(
        task_id="api_is_up",
        http_conn_id=MARINE_CONN_ID,
        endpoint=marine.MARINE_ENDPOINT,
        request_params={"latitude": 0, "longitude": 0, "hourly": "wave_height", "forecast_days": 1},
        response_check=lambda response: "hourly" in response.json(),
        mode="reschedule",
        poke_interval=60,
        timeout=10 * 60,
    )

    @task
    def create_table() -> None:
        SqliteHook(sqlite_conn_id=DB_CONN_ID).run(storage.CREATE_TABLE)

    @task
    def get_target_day() -> str:
        # get_current_context() exposes the run's metadata (the same values
        # you can use in Jinja templates like {{ data_interval_start }}).
        ctx = get_current_context()
        # With CronDataIntervalTimetable, scheduled/backfill runs have
        # logical_date == data_interval_start. Manual runs (`airflow dags test
        # DAG 2026-10-10`, UI trigger) get the date you chose as logical_date, but
        # their data interval is *inferred* as the one ENDING then (Oct 9!), so
        # logical_date is the field that means "the day I asked for" everywhere.
        start = ctx.get("logical_date")
        if start is None:  # manual run triggered without a logical date
            start = ctx["dag_run"].run_after - timedelta(days=1)
        if start.date() >= pendulum.now("UTC").date():
            # Today isn't over yet; the API would return a partial forecast.
            # AirflowFailException fails the task immediately, skipping retries:
            # use it for errors that retrying can't fix.
            raise AirflowFailException(f"Refusing to process incomplete day {start.date()}")
        return start.strftime("%Y-%m-%d")

    @task
    def get_spots() -> list[dict]:
        # Read Variables INSIDE tasks, not at the top of the file: top-level
        # code runs on every DAG parse (every ~30s), not just at execution.
        return Variable.get("surf_spots", deserialize_json=True)

    @task(max_active_tis_per_dagrun=MAX_PARALLEL_API_CALLS)
    def fetch(spot: dict, day: str) -> dict:
        response = HttpHook(method="GET", http_conn_id=MARINE_CONN_ID).run(
            endpoint=marine.MARINE_ENDPOINT,
            data=marine.build_params(spot, day),  # for GET, `data` = query params
        )
        return {"spot": spot["name"], "payload": response.json()}

    @task
    def transform(raw: dict) -> list[dict]:
        rows = marine.to_rows(raw["spot"], raw["payload"])
        print(f"{raw['spot']}: {len(rows)} hourly rows")
        return rows

    @task
    def validate(rows: list[dict]) -> list[dict]:
        spot = rows[0]["spot"] if rows else "unknown spot"
        problems = quality.find_problems(spot, rows)
        if problems:
            # Bad data won't fix itself on retry, so fail immediately and loudly.
            raise AirflowFailException("Data-quality check failed: " + "; ".join(problems))
        return rows

    @task(outlets=[SURF_CONDITIONS])
    def load(rows_per_spot: list[list[dict]], day: str) -> int:
        # A mapped task's output arrives downstream as a list (one item per spot).
        rows = [
            tuple(row[col] for col in storage.COLUMNS)
            for spot_rows in rows_per_spot
            for row in spot_rows
        ]
        SqliteHook(sqlite_conn_id=DB_CONN_ID).insert_rows(
            table="surf_conditions",
            rows=rows,
            target_fields=list(storage.COLUMNS),
            replace=True,
        )
        # Attach metadata to the asset event; consumers (04_publish_snapshot)
        # read it to know which day changed.
        get_current_context()["outlet_events"][SURF_CONDITIONS].extra = {"day": day}
        return len(rows)

    # --- Wiring --------------------------------------------------------------
    day = get_target_day()
    spots = get_spots()
    # partial() = same for every mapped instance; expand() = one instance per item.
    raw = fetch.partial(day=day).expand(spot=spots)
    rated = transform.expand(raw=raw)  # map over a mapped output: 1 transform per fetch
    checked = validate.expand(rows=rated)

    [api_is_up, create_table()] >> raw
    load(checked, day)


surf_etl()
