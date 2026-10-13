"""Plain-Python helpers for the surf DAGs.

Airflow adds the dags/ folder to sys.path, so DAG files can `import surf_lib`.
Keeping business logic here (not in the DAG files) makes it unit-testable without
Airflow and keeps DAG files fast to parse.
"""
