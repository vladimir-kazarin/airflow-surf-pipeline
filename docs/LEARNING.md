# Learning guide: Apache Airflow 3 through one small pipeline

This repo doubles as a hands-on Airflow course. Every day the pipeline fetches hourly
wave data for four surf breaks (Cape Cod, Bali, Morocco, Hawaii) from the free
[Open-Meteo Marine API](https://open-meteo.com/en/docs/marine-weather-api), rates each hour
(FLAT / POOR / FAIR / GOOD / HAZARDOUS), loads it into SQLite, writes a "should I go
surf?" report, and publishes to S3 for the dashboard.

Airflow 3.3.2 · Python 3.12 · runs locally, no Docker. AWS is optional (lesson 4 skips
cleanly without it).

## Quickstart

```bash
cd ~/dev/airflow
./scripts/setup.sh          # only once (already done for you)
./scripts/start.sh          # all components in one process, UI at http://localhost:8081
./scripts/stop.sh           # stop everything (including orphaned workers)
```

Login: `admin`, password from `cat .airflow/simple_auth_manager_passwords.json.generated`.

For CLI commands in another terminal, run `source env.sh` first.

## The mental model (read this first)

```
            dags/*.py
                │  parsed every 30s
        ┌───────▼────────┐   serialized DAGs   ┌──────────────┐
        │ dag-processor  │ ──────────────────► │  metadata DB │ ◄── UI / REST API (api-server)
        └────────────────┘                     │ (SQLite here)│
        ┌────────────────┐   creates DagRuns,  └──────▲───────┘
        │   scheduler    │ ── queues tasks ──────────┘
        └───────┬────────┘
                │ LocalExecutor
        ┌───────▼────────┐   task state / XCom / Variables / Connections
        │ worker procs   │ ──── via the api-server's "execution API" ───►
        └────────────────┘
        triggerer: runs async "deferred" waits (not used here)
```

Things that trip people up:

1. **A DAG file is a config file written in Python.** It's executed every ~30s just to
   build the graph. Don't put work (API calls, `Variable.get`) at the top level.
   Put it inside tasks.
2. **Tasks are isolated.** Each runs in its own process, maybe on another machine.
   They share data only through **XCom** (small values) or external storage (the DB).
3. **Logical date ≠ when it ran.** A run *represents* a period of data. Use the
   context (`logical_date`, `data_interval_start`) instead of `datetime.now()`, and every run becomes
   reproducible and backfillable.
4. **Tasks should be idempotent.** Running twice must give the same result. That's
   what makes retries and backfills safe (here: `REPLACE INTO` on a primary key).

## Lessons, in order

### Lesson 1: `dags/01_hello_surf.py`
DAG · operators vs `@task` · `>>` dependencies · XCom · Jinja templating.

- In the UI, open **01_hello_surf**, unpause it, press ▶ (Trigger).
- Click the run → **Graph**. Click `paddle_out` → **Logs**: see "Paddling out at Montauk".
- Click `pick_spot` → **XCom**: the return value stored in the DB.
- Click `wax_board` → **Rendered Templates**: `{{ run_id }}` filled in.

### Lesson 2: `dags/02_surf_etl.py`
Schedules & data intervals · backfill · sensors · Connections · Variables · dynamic task
mapping (`partial`/`expand`) · retries · data-quality gate · idempotent loads · Asset
outlets with `extra`.

- Graph view: `fetch` and `transform` show `[4]`, one mapped instance per spot.
  Click one → **Mapped Tasks** tab.
- Run a backfill and watch runs appear in the grid:
  ```bash
  source env.sh
  airflow backfill create --dag-id 02_surf_etl --from-date 2026-10-01 --to-date 2026-10-05
  ```
- See where config lives: `env.sh` defines the Connections (`AIRFLOW_CONN_*`) and
  Variables (`AIRFLOW_VAR_*`). The code only references ids.

**Airflow 3 gotcha we hit while building this:** a plain cron string (`"@daily"`) now means
`CronTriggerTimetable`: the logical date is the moment it fires. Our first scheduled run
on Oct 13 therefore fetched *today's incomplete* data. "Process the day that just ended"
needs `CronDataIntervalTimetable` (the Airflow 2 behaviour), now set explicitly in the DAG.
Also note that run ids are named after `run_after`: `backfill__2026-10-10…` is the run
*for* Oct 9.

**Second date gotcha:** for *manual* runs (`airflow dags test 02_surf_etl 2026-10-10`, the
UI's trigger button) Airflow *infers* the data interval as the one **ending** at the date
you chose, so `data_interval_start` is Oct 9. `logical_date` is Oct 10 for manual,
scheduled and backfill runs alike, so `get_target_day` reads `logical_date`.

**SQLite lesson:** creating a 100-day backfill while the scheduler was running failed with
`database is locked`. SQLite allows one writer at a time; that's why production Airflow
uses Postgres. For local seeding: `./scripts/stop.sh`, create the backfill, start again.

### Lesson 3: `dags/03_surf_report.py`
Asset (data-aware) scheduling · `@task.branch` · trigger rules · explicit `xcom_pull`.

- It has no cron. It runs whenever `02_surf_etl.load` succeeds. Check the **Assets** page.
- Open a run: one of `go_surf` / `stay_home` is pink (**skipped**), yet `write_report` ran
  thanks to `trigger_rule="none_failed_min_one_success"`.
- Several asset events that arrive close together are consumed by **one** report run
  (a 2-day backfill + 1 scheduled run → 1 report).
- Read the output: `cat data/reports/*.md`

### Lesson 4: `dags/04_publish_snapshot.py`
Provider hooks (`S3Hook`) · one Asset, two consumers · asset event `extra` ·
`AirflowSkipException` · keeping big data out of XCom.

- Runs alongside 03 on the same asset event. It reads which days changed from
  `triggering_asset_events` (02's `load` attached `{"day": ...}`), so it only rewrites those
  S3 objects.
- Without AWS (`SURF_BUCKET` unset) every task is pink/**skipped** and the run is still green.
- With AWS: `terraform -chdir=infra apply`, then put `SURF_BUCKET=...` and
  `SURF_AWS_PROFILE=...` in `.env.local` and restart.
- In production the same DAGs run in GitHub Actions (`.github/workflows/daily-pipeline.yml`)
  via `airflow dags test`, which has no scheduler, so 04 is invoked explicitly there.

## Where each concept lives

| Concept | Where |
|---|---|
| DAG definition, `@dag` / `@task` | `01_hello_surf.py` |
| Classic operator + Jinja | `BashOperator` in `01_hello_surf.py` |
| XCom (implicit / explicit) | `pick_spot` → `paddle_out`; `ti.xcom_pull` in `03_surf_report.py` |
| Timetable / data interval | `schedule=CronDataIntervalTimetable(...)`, `get_target_day` in `02` |
| Sensor (reschedule mode) | `api_is_up` in `02` |
| Connections & hooks | `HttpHook`, `SqliteHook` in `02`; definitions in `env.sh` |
| Variables | `get_spots` in `02`, `surf_report_dir` in `03` |
| Dynamic task mapping | `fetch.partial(day=day).expand(spot=spots)` in `02` |
| Retries / backoff / timeout | `default_args` in `02` |
| Fail without retrying | `AirflowFailException` in `get_target_day` |
| Assets (data-aware scheduling) | `surf_lib/assets.py`, `outlets=` in `02`, `schedule=[...]` in `03` |
| Branching + trigger rules | `decide`, `write_report` in `03` |
| Data-quality gate | `validate` in `02`, rules in `surf_lib/quality.py` |
| Provider hook for cloud storage | `S3Hook` in `04`, `aws_default` Connection in `env.sh` |
| Asset event extras | `outlet_events[...].extra` in `02`, `triggering_asset_events` in `04` |
| Skipping a run on purpose | `AirflowSkipException` in `04.get_bucket` |
| Keep logic out of DAG files | `dags/surf_lib/` (+ `.airflowignore`) |
| Testing DAGs | `tests/test_dags.py` (DagBag), `airflow dags test` |

## Exercises (do them in order)

1. **Add a spot.** Add your favourite break to `AIRFLOW_VAR_SURF_SPOTS` in `env.sh`,
   restart, trigger `02_surf_etl`. The mapped task now has 5 instances with no code change.
2. **Break it on purpose.** Set a spot's latitude to `999`. Watch `fetch` retry with
   backoff in the logs, then fail. Then fix it and use **Clear** on the failed task to
   re-run just that task.
3. **Idempotency check.** Clear a successful `02_surf_etl` run. Confirm the row count in
   `data/surf.db` doesn't change.
4. **Add a task.** After `load`, add a `@task` that logs the day's max wave height per
   spot (query with `SqliteHook`). Write a unit test for any pure logic you add.
5. **Use a template instead of context.** Replace `get_target_day` by passing
   `day="{{ ds }}"` into `fetch.partial(...)`. Why does that work? (Hint: `@task`
   arguments are templated.)
6. **Wind.** Add `wind_wave_height` to `HOURLY_FIELDS`, a column to the table, and make
   the rating penalise choppy wind swell. Backfill a week and compare reports.
7. **Stretch: deferrable sensor.** Set `deferrable=True` on `api_is_up` and watch it
   hand its wait to the triggerer (the purple "deferred" state).

## Cheat sheet

```bash
source env.sh
pytest                                        # unit + DAG integrity tests
airflow dags test 02_surf_etl 2026-10-10      # run a whole DAG in-process, no scheduler: best debug loop
airflow tasks test 02_surf_etl get_spots 2026-10-10   # run ONE task, no state saved
airflow dags list-import-errors               # why isn't my DAG showing up?
airflow dags list-runs 02_surf_etl
airflow backfill create --dag-id 02_surf_etl --from-date 2026-10-01 --to-date 2026-10-05
python -c "import sqlite3; [print(r) for r in sqlite3.connect('data/surf.db').execute('select spot, ts, wave_height, rating from surf_conditions limit 10')]"
```

## Layout

```
env.sh                 all config: paths, port, Connections, Variables
dags/
  01_hello_surf.py     lesson 1
  02_surf_etl.py       lesson 2
  03_surf_report.py    lesson 3
  04_publish_snapshot.py  lesson 4
  surf_lib/            plain Python (rating, API parsing, quality, SQL, S3 layout), unit-tested
  .airflowignore       stop the scheduler parsing surf_lib as DAGs
tests/                 pytest: DAG integrity + logic
app/                   Streamlit dashboard (own requirements.txt, own tests)
infra/                 Terraform: S3 bucket, GitHub OIDC role, dashboard read-only user
.github/workflows/     CI + the daily production run
scripts/               setup / start / stop
.env.local             your bucket / AWS profile (gitignored)
data/                  surf.db + reports (generated)
.airflow/              Airflow's own home: metadata DB, logs, passwords (generated)
```
