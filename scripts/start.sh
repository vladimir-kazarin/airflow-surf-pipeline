#!/usr/bin/env bash
# Starts every Airflow component in one process (dev only):
# api-server (UI, port set in env.sh), scheduler, dag-processor, triggerer.
set -euo pipefail
cd "$(dirname "$0")/.."
source env.sh

PASSWORDS_FILE="$AIRFLOW_HOME/simple_auth_manager_passwords.json.generated"
echo "UI: http://localhost:$AIRFLOW_PORT  (login: admin; password is printed below / stored in $PASSWORDS_FILE)"
exec airflow standalone
