#!/usr/bin/env sh
# Smoke test for the db-bootstrap template (ADR-0003): the script must be
# idempotent (IF NOT EXISTS semantics), use the engine client (psql), and
# contain no app-schema DDL.
set -eu

SCRIPT="$(dirname "$0")/../../../src/bootstrap.sh"
[ -f "$SCRIPT" ] || { echo "FAIL: $SCRIPT missing"; exit 1; }

grep -q "IF NOT EXISTS\|NOT EXISTS (SELECT FROM pg_database\|CREATE DATABASE" "$SCRIPT" \
  || { echo "FAIL: bootstrap.sh lacks idempotent CREATE DATABASE semantics"; exit 1; }
grep -q "psql" "$SCRIPT" \
  || { echo "FAIL: bootstrap.sh must use the engine client (psql)"; exit 1; }
if grep -qE "CREATE TABLE|ALTER TABLE|INSERT INTO" "$SCRIPT"; then
  echo "FAIL: bootstrap.sh must not contain app-schema DDL"
  exit 1
fi

echo "OK: db-bootstrap template contract"
