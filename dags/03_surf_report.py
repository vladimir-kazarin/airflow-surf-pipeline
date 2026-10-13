"""
### Lesson 3: data-aware scheduling, branching, trigger rules

Runs automatically whenever `02_surf_etl` updates the `surf_conditions` asset.
Finds each spot's best hour for the latest day, decides go/no-go, and writes
`data/reports/<day>.md`.

Concepts:
- **Asset schedule**: `schedule=[SURF_CONDITIONS]`, no cron. This DAG runs
  because upstream data changed.
- **Branching**: `@task.branch` returns the task_id(s) to run next; the other
  branch is marked *skipped*.
- **Trigger rules**: `write_report` must run after whichever branch ran. With
  the default `all_success` it would be skipped too (a skipped upstream is not
  a success), so it uses `none_failed_min_one_success`.
- **Explicit XCom pull**: `ti.xcom_pull(...)` reads another task's output
  without creating a data dependency (handy when one upstream was skipped).
"""

from pathlib import Path

import pendulum
from airflow.providers.sqlite.hooks.sqlite import SqliteHook
from airflow.sdk import Variable, dag, get_current_context, task

from surf_lib import report, storage
from surf_lib.assets import SURF_CONDITIONS

DB_CONN_ID = "surf_db"
BRANCH_TASK_IDS = ["go_surf", "stay_home"]


@dag(
    dag_id="03_surf_report",
    schedule=[SURF_CONDITIONS],
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    tags=["surf", "lesson-3"],
    doc_md=__doc__,
)
def surf_report():
    @task
    def find_best_sessions() -> dict:
        hook = SqliteHook(sqlite_conn_id=DB_CONN_ID)
        day = hook.get_first(storage.LATEST_DAY)[0]
        if day is None:
            raise ValueError("surf_conditions is empty. Run 02_surf_etl first.")
        rows = hook.get_records(storage.DAY_ROWS, parameters=(day,))
        return {"day": day, "sessions": report.best_sessions(rows)}

    @task.branch
    def decide(best: dict) -> str:
        return "go_surf" if report.has_surfable(best["sessions"]) else "stay_home"

    @task
    def go_surf(best: dict) -> str:
        top = best["sessions"][0]
        verdict = f"Go surf at {top['spot']} around {top['ts'][11:16]} UTC ({top['rating']})"
        print(verdict)
        return verdict

    @task
    def stay_home() -> str:
        verdict = "Nothing worth paddling out for. Stay home and wax the board."
        print(verdict)
        return verdict

    @task(trigger_rule="none_failed_min_one_success")
    def write_report(best: dict) -> str:
        ti = get_current_context()["ti"]
        # The skipped branch pushed nothing, so keep whichever verdict exists.
        verdicts = ti.xcom_pull(task_ids=BRANCH_TASK_IDS) or []
        verdict = next((v for v in verdicts if v), "No verdict")

        out_dir = Path(Variable.get("surf_report_dir"))
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{best['day']}.md"
        path.write_text(report.render_markdown(best["day"], best["sessions"], verdict))
        print(f"Wrote {path}")
        return str(path)

    best = find_best_sessions()
    branches = [go_surf(best), stay_home()]
    decide(best) >> branches >> write_report(best)


surf_report()
