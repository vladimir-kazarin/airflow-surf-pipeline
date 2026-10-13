"""
### Lesson 1: DAG, tasks, operators, dependencies, XCom

Trigger this manually (the ▶ button). It has no schedule.

Concepts:
- **DAG**: a Python-defined graph of tasks. Airflow only parses this file; it
  doesn't run your logic until a task executes.
- **Operator**: a template for a task (`BashOperator` runs a shell command).
- **TaskFlow `@task`**: turns a plain Python function into a task.
- **Dependencies**: `a >> b` means "b runs after a succeeds".
- **XCom**: a `@task`'s return value is stored in the metadata DB and passed
  to downstream tasks that take it as an argument.
- **Jinja templating**: `{{ run_id }}` is filled in at runtime.
"""

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task


@dag(
    dag_id="01_hello_surf",
    schedule=None,  # no schedule: runs only when you trigger it
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    tags=["surf", "lesson-1"],
    doc_md=__doc__,  # shows up in the UI's "Docs" panel
)
def hello_surf():
    # A classic operator. The command string is a Jinja template.
    wax_board = BashOperator(
        task_id="wax_board",
        bash_command='echo "Waxing the board for run {{ run_id }}"',
    )

    @task
    def pick_spot() -> str:
        # Returning a value pushes it to XCom (key "return_value").
        return "Montauk"

    @task
    def paddle_out(spot: str) -> None:
        # Passing pick_spot()'s output in pulls it from XCom AND creates the
        # dependency pick_spot >> paddle_out automatically.
        print(f"Paddling out at {spot} 🏄")

    spot = pick_spot()
    wax_board >> spot  # explicit dependency (no data passed)
    paddle_out(spot)


# Calling the decorated function registers the DAG.
hello_surf()
