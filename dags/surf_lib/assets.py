"""Assets shared between DAGs.

An Asset is a logical name for a piece of data. A task that lists it in
`outlets=` emits an "asset event" when it succeeds; a DAG with
`schedule=[asset]` runs whenever that event happens. This is how one DAG
triggers another without knowing about it ("data-aware scheduling").
"""

from airflow.sdk import Asset

SURF_CONDITIONS = Asset("surf_conditions")
