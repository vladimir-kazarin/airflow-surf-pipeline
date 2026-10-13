#!/usr/bin/env bash
# One-time setup: venv + Airflow pinned with the official constraints file.
set -euo pipefail
cd "$(dirname "$0")/.."

AIRFLOW_VERSION=3.3.2
PYTHON_VERSION=3.12
CONSTRAINTS="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

uv venv --python "$PYTHON_VERSION" .venv
uv pip install --python .venv/bin/python \
    "apache-airflow==${AIRFLOW_VERSION}" \
    apache-airflow-providers-http \
    apache-airflow-providers-sqlite \
    apache-airflow-providers-amazon \
    pytest \
    --constraint "$CONSTRAINTS"

source env.sh
airflow db migrate
echo "Done. Next: ./scripts/start.sh"
