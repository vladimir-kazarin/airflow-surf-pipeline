"""DAG integrity tests: the cheapest, most valuable Airflow tests.

They catch import errors, cycles, and missing config before the scheduler does.
Run with:  source env.sh && pytest
"""

import pytest
from airflow.dag_processing.dagbag import DagBag

EXPECTED_DAGS = {"01_hello_surf", "02_surf_etl", "03_surf_report", "04_publish_snapshot"}


@pytest.fixture(scope="session")
def dagbag() -> DagBag:
    return DagBag()  # parses AIRFLOW__CORE__DAGS_FOLDER, like the scheduler does


def test_no_import_errors(dagbag):
    assert dagbag.import_errors == {}


def test_expected_dags_present(dagbag):
    assert EXPECTED_DAGS <= set(dagbag.dag_ids)


def test_every_dag_is_tagged_and_documented(dagbag):
    for dag_id in EXPECTED_DAGS:
        dag = dagbag.get_dag(dag_id)
        assert dag.tags, f"{dag_id} has no tags"
        assert dag.doc_md, f"{dag_id} has no doc_md"


def test_etl_tasks_retry(dagbag):
    dag = dagbag.get_dag("02_surf_etl")
    assert all(t.retries >= 1 for t in dag.tasks)


def test_etl_processes_completed_intervals(dagbag):
    # Logical date must be the START of the day being processed, not "now".
    dag = dagbag.get_dag("02_surf_etl")
    assert type(dag.timetable).__name__ == "CronDataIntervalTimetable"


def test_etl_wiring(dagbag):
    dag = dagbag.get_dag("02_surf_etl")
    assert dag.get_task("fetch").upstream_task_ids >= {"api_is_up", "create_table", "get_spots"}
    assert dag.get_task("validate").upstream_task_ids == {"transform"}
    assert dag.get_task("load").upstream_task_ids == {"validate", "get_target_day"}


def test_publish_and_report_both_consume_the_asset(dagbag):
    for dag_id in ("03_surf_report", "04_publish_snapshot"):
        assert "surf_conditions" in repr(dagbag.get_dag(dag_id).timetable.asset_condition)
