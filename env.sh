# Source this in every shell you use for this project:  source env.sh
# It activates the venv and configures Airflow purely through environment variables.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PROJECT_DIR/.venv/bin/activate"

# Where Airflow keeps its own state: config, metadata DB (SQLite), logs.
export AIRFLOW_HOME="$PROJECT_DIR/.airflow"
# Where the scheduler looks for DAG files.
export AIRFLOW__CORE__DAGS_FOLDER="$PROJECT_DIR/dags"
# Hide the ~50 bundled example DAGs so the UI only shows ours.
export AIRFLOW__CORE__LOAD_EXAMPLES=False
# Re-scan the DAGs folder every 30s so your edits show up quickly.
export AIRFLOW__DAG_PROCESSOR__REFRESH_INTERVAL=30
# UI/API port. 8080 is often taken (kubectl port-forward), so use 8081.
# Task workers talk to the API server's "execution API" too, so point them at it.
export AIRFLOW_PORT=8081
export AIRFLOW__API__PORT=$AIRFLOW_PORT
export AIRFLOW__API__BASE_URL="http://localhost:$AIRFLOW_PORT"
export AIRFLOW__CORE__EXECUTION_API_SERVER_URL="http://localhost:$AIRFLOW_PORT/execution/"

# --- Connections -------------------------------------------------------------
# Any env var named AIRFLOW_CONN_<CONN_ID> defines a Connection. Hooks/operators
# refer to it by conn_id ("open_meteo_marine", "surf_db"), never by URL, so the
# same DAG code can point at dev/prod just by changing config.
export AIRFLOW_CONN_OPEN_METEO_MARINE='{"conn_type": "http", "host": "marine-api.open-meteo.com", "schema": "https"}'
mkdir -p "$PROJECT_DIR/data"
export AIRFLOW_CONN_SURF_DB="{\"conn_type\": \"sqlite\", \"host\": \"$PROJECT_DIR/data/surf.db\"}"

# --- Variables ---------------------------------------------------------------
# AIRFLOW_VAR_<KEY> defines a Variable. Edit the spots here and restart, and
# the pipeline fans out over the new list. (Env-var Variables take precedence
# over ones created in the UI, so change them here, not in Admin -> Variables.)
export AIRFLOW_VAR_SURF_SPOTS='[
  {"name": "Montauk",      "latitude": 41.03, "longitude": -71.93},
  {"name": "Rockaway",     "latitude": 40.58, "longitude": -73.82},
  {"name": "Outer Banks",  "latitude": 35.56, "longitude": -75.46},
  {"name": "Cocoa Beach",  "latitude": 28.32, "longitude": -80.60}
]'
export AIRFLOW_VAR_SURF_REPORT_DIR="$PROJECT_DIR/data/reports"

# --- Publishing to S3 (DAG 04) ----------------------------------------------
# Machine-specific settings live in .env.local (gitignored), e.g.:
#   SURF_BUCKET=airflow-surf-pipeline-123456789012
#   SURF_AWS_PROFILE=terraform
[ -f "$PROJECT_DIR/.env.local" ] && source "$PROJECT_DIR/.env.local"

# Empty bucket => DAG 04 skips, so the learning setup works without AWS.
export AIRFLOW_VAR_SURF_BUCKET="${SURF_BUCKET:-}"
export AIRFLOW_VAR_SURF_PUBLISH_SOURCE="${SURF_PUBLISH_SOURCE:-local}"
# With a profile, boto3 uses ~/.aws; without one (CI) it uses the standard
# AWS_* env vars that GitHub's OIDC login sets.
if [ -n "${SURF_AWS_PROFILE:-}" ]; then
    export AIRFLOW_CONN_AWS_DEFAULT="{\"conn_type\": \"aws\", \"extra\": {\"region_name\": \"${SURF_AWS_REGION:-us-east-1}\", \"profile_name\": \"$SURF_AWS_PROFILE\"}}"
else
    export AIRFLOW_CONN_AWS_DEFAULT="{\"conn_type\": \"aws\", \"extra\": {\"region_name\": \"${SURF_AWS_REGION:-us-east-1}\"}}"
fi
