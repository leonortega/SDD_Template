#!/usr/bin/env sh
# db-bootstrap: engine-level bootstrap Job (ADR-0003).
#
# Creates logical databases, roles, and extensions on the shared engine —
# nothing else. Deliberately knows NO app schema: per-app schema migrations
# run via each app's migration-job.yaml.
#
# Idempotent (IF NOT EXISTS semantics): re-runnable after a kind cluster
# recreation — the engine's PVC dies with the cluster, so logical databases
# must be recreated. The AI scaffold rewrites this script for the engine
# selected in project-profile.local.json -> stack.database (shipped: Postgres).
set -eu

DB_HOST="${DB_HOST:-db.internal}"
DB_PORT="${DB_PORT:-5432}"
DB_ADMIN_USER="${DB_ADMIN_USER:-postgres}"
DB_ADMIN_PASSWORD="${DB_ADMIN_PASSWORD:-postgres}"
# Space-separated logical databases owned by the project (engine-level only).
BOOTSTRAP_DATABASES="${BOOTSTRAP_DATABASES:-orders storefront}"

export PGPASSWORD="$DB_ADMIN_PASSWORD"

for db in $BOOTSTRAP_DATABASES; do
  echo "bootstrap: ensuring logical database '$db'"
  psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_ADMIN_USER" -d postgres \
    --set=db="$db" <<'SQL'
SELECT 'CREATE DATABASE'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db')\gexec
SQL
done

echo "db-bootstrap complete"
