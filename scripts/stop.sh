#!/usr/bin/env bash
# Stops every Airflow process started by start.sh, including the children
# that rename themselves ("airflow api_server", "airflow worker -- LocalExecutor").
set -uo pipefail

GRACE_SECONDS=10

airflow_pids() {
    ps -eo pid=,args= | awk '$2 == "airflow" || $0 ~ /\.venv\/bin\/airflow/ {print $1}'
}

pids=$(airflow_pids)
[ -z "$pids" ] && { echo "Airflow is not running."; exit 0; }

kill $pids 2>/dev/null
for _ in $(seq 1 "$GRACE_SECONDS"); do
    [ -z "$(airflow_pids)" ] && { echo "Airflow stopped."; exit 0; }
    sleep 1
done

echo "Some processes ignored SIGTERM; forcing."
airflow_pids | xargs -r kill -9 2>/dev/null
echo "Airflow stopped."
