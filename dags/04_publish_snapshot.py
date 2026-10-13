"""
### Lesson 4: publishing to S3 for the dashboard

Runs whenever `02_surf_etl` updates the `surf_conditions` asset (in parallel
with `03_surf_report`: one asset, two consumers). Writes the changed days to
S3 as one CSV per day, then rebuilds the compact files the Streamlit app reads.

Concepts:
- **Provider hooks**: `S3Hook` from `apache-airflow-providers-amazon`, using
  the `aws_default` Connection. Locally that's an AWS profile; in GitHub Actions
  it's short-lived OIDC credentials. The DAG code is identical.
- **Asset event extras**: `triggering_asset_events` tells us *which* days
  changed (02 put the day in the event's `extra`).
- **Skipping**: no bucket configured means `AirflowSkipException`. The run is green,
  its tasks pink (skipped), so the local learning setup works without AWS.
- **Big data doesn't go through XCom**: rows go DB -> S3 inside one task; only
  small summaries are returned.
"""

import pendulum
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.sqlite.hooks.sqlite import SqliteHook
from airflow.sdk import Variable, dag, get_current_context, task
from airflow.sdk.exceptions import AirflowSkipException

from surf_lib import publish, storage
from surf_lib.assets import SURF_CONDITIONS

DB_CONN_ID = "surf_db"
AWS_CONN_ID = "aws_default"
ALL_ROWS = f"SELECT {', '.join(storage.COLUMNS)} FROM surf_conditions"


def _changed_days() -> set[str]:
    """Days announced by the asset events that triggered this run (empty for manual runs)."""
    events = get_current_context().get("triggering_asset_events") or {}
    return {
        event.extra["day"]
        for asset_events in events.values()
        for event in asset_events
        if event.extra and event.extra.get("day")
    }


@dag(
    dag_id="04_publish_snapshot",
    schedule=[SURF_CONDITIONS],
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,  # two concurrent rebuilds of the serving file would race
    default_args={"retries": 2},
    tags=["surf", "lesson-4", "s3"],
    doc_md=__doc__,
)
def publish_snapshot():
    @task
    def get_bucket() -> str:
        bucket = Variable.get("surf_bucket", default="")
        if not bucket:
            raise AirflowSkipException("Variable surf_bucket is empty; nothing to publish.")
        return bucket

    @task
    def get_spots() -> list[dict]:
        return Variable.get("surf_spots", deserialize_json=True)

    @task
    def write_partitions(bucket: str, spots: list[dict]) -> list[str]:
        names = [s["name"] for s in spots]
        placeholders = ", ".join("?" for _ in names)
        rows = SqliteHook(sqlite_conn_id=DB_CONN_ID).get_records(
            f"{ALL_ROWS} WHERE spot IN ({placeholders})", parameters=names
        )
        by_day = publish.group_by_day(rows)
        # Event-triggered: only the days that changed. Manual / CI run: every day in the DB.
        days = sorted(_changed_days() & by_day.keys() or by_day.keys())

        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        for day in days:
            s3.load_string(
                publish.to_csv(by_day[day]),
                key=publish.partition_key(day),
                bucket_name=bucket,
                replace=True,
            )
        print(f"Wrote {len(days)} partition(s): {days}")
        return days

    @task
    def build_serving(bucket: str, days: list[str], spots: list[dict]) -> dict:
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        keys = sorted(s3.list_keys(bucket_name=bucket, prefix=publish.CONDITIONS_PREFIX))
        all_rows = [row for key in keys for row in publish.parse_csv(s3.read_key(key, bucket))]
        # Older partitions may still hold spots that were removed from the config.
        rows = publish.only_spots(all_rows, (s["name"] for s in spots))

        ctx = get_current_context()
        now = pendulum.now("UTC").isoformat(timespec="seconds")
        meta = publish.build_meta(
            rows,
            generated_at=now,
            source=Variable.get("surf_publish_source", default="local"),
            run_id=ctx["run_id"],
            spot_info=spots,
        )
        s3.load_string(
            publish.to_csv([r[c] for c in storage.COLUMNS] for r in rows),
            key=publish.SERVING_KEY,
            bucket_name=bucket,
            replace=True,
        )
        s3.load_string(publish.to_json(meta), key=publish.META_KEY, bucket_name=bucket, replace=True)

        previous_runs = (
            s3.read_key(publish.RUNS_KEY, bucket)
            if s3.check_for_key(publish.RUNS_KEY, bucket)
            else None
        )
        entry = {
            "published_at": now,
            "source": meta["source"],
            "run_id": meta["run_id"],
            "days_published": ";".join(days),
            "rows_total": meta["rows"],
            "last_day": meta["last_day"],
        }
        s3.load_string(
            publish.append_run(previous_runs, entry),
            key=publish.RUNS_KEY,
            bucket_name=bucket,
            replace=True,
        )
        return meta

    bucket = get_bucket()
    spots = get_spots()
    build_serving(bucket, write_partitions(bucket, spots), spots)


publish_snapshot()
