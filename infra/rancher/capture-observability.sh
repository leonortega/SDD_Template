#!/usr/bin/env bash
set -euo pipefail

environment=""
namespace=""
commit_sha=""
site_image=""
api_image=""
site_url=""
api_url=""
output_dir="artifacts/rancher-observability"
if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
  default_seq_url="http://host.docker.internal:5341"
else
  default_seq_url="http://localhost:5341"
fi
seq_url="${SEQ_URL:-$default_seq_url}"
observability_enabled="${RANCHER_OBSERVABILITY_ENABLED:-true}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --environment) environment="$2"; shift 2 ;;
    --namespace) namespace="$2"; shift 2 ;;
    --commit-sha) commit_sha="$2"; shift 2 ;;
    --site-image) site_image="$2"; shift 2 ;;
    --api-image) api_image="$2"; shift 2 ;;
    --site-url) site_url="$2"; shift 2 ;;
    --api-url) api_url="$2"; shift 2 ;;
    --output-dir) output_dir="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

test -n "$environment"
test -n "$namespace"
test -n "$commit_sha"
test -n "$site_image"
test -n "$api_image"
test -n "$site_url"
test -n "$api_url"

if ! kubectl config current-context | grep -qx "rancher-desktop"; then
  echo "kubectl current context must be rancher-desktop." >&2
  exit 1
fi

site_digest="${site_image##*@}"
api_digest="${api_image##*@}"
checked_at_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p "$output_dir"

capture_health() {
  local name="$1"
  local url="$2"
  local output="$output_dir/${name}-health.json"
  local status_file="$output_dir/${name}-health.status"

  if curl --fail --silent --show-error --location "$url" -o "$output"; then
    printf 'PASS\n' > "$status_file"
  else
    printf 'FAIL\n' > "$status_file"
    return 1
  fi
}

sanitize_logs() {
  sed -E \
    -e 's/(password|passwd|pwd|token|secret|api[_-]?key|authorization|connectionstring|connection string)([=: ][^[:space:]]*)/\1=<redacted>/Ig' \
    -e 's/(Bearer )[A-Za-z0-9._~+\/=-]+/\1<redacted>/Ig'
}

capture_logs() {
  local app="$1"
  local raw="$output_dir/${app}-pod.log"
  local sanitized="$output_dir/${app}-pod.sanitized.log"

  kubectl -n "$namespace" logs "deployment/${app}" --tail=120 --all-containers=true > "$raw" 2>&1 || true
  sanitize_logs < "$raw" > "$sanitized"
}

post_logs_to_seq() {
  local app="$1"
  local digest="$2"
  local log_file="$output_dir/${app}-pod.sanitized.log"
  local clef_file="$output_dir/${app}-seq.clef"

  : > "$clef_file"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    jq -cn \
      --arg t "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg mt "{App} Kubernetes log: {Message}" \
      --arg message "$line" \
      --arg environment "${environment^^}" \
      --arg namespace "$namespace" \
      --arg app "$app" \
      --arg commitSha "$commit_sha" \
      --arg imageDigest "$digest" \
      '{
        "@t": $t,
        "@mt": $mt,
        Message: $message,
        Environment: $environment,
        Provider: "rancher-desktop",
        Namespace: $namespace,
        App: $app,
        CommitSha: $commitSha,
        ImageDigest: $imageDigest
      }' >> "$clef_file"
  done < "$log_file"

  if [ ! -s "$clef_file" ]; then
    jq -cn \
      --arg t "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg environment "${environment^^}" \
      --arg namespace "$namespace" \
      --arg app "$app" \
      --arg commitSha "$commit_sha" \
      --arg imageDigest "$digest" \
      '{
        "@t": $t,
        "@mt": "{App} Kubernetes log collection completed with no recent lines",
        Environment: $environment,
        Provider: "rancher-desktop",
        Namespace: $namespace,
        App: $app,
        CommitSha: $commitSha,
        ImageDigest: $imageDigest
      }' > "$clef_file"
  fi

  curl --fail --silent --show-error \
    -H "Content-Type: application/vnd.serilog.clef" \
    --data-binary "@$clef_file" \
    "${seq_url%/}/ingest/clef" >/dev/null
}

site_health_status="FAIL"
api_health_status="FAIL"
seq_recent_log_status="SKIPPED"

capture_health site "${site_url%/}/health" && site_health_status="PASS"
capture_health api "${api_url%/}/health" && api_health_status="PASS"
capture_logs site
capture_logs api

if [ "$observability_enabled" = "true" ]; then
  curl --fail --silent --show-error "${seq_url%/}/api" >/dev/null
  post_logs_to_seq site "$site_digest"
  post_logs_to_seq api "$api_digest"
  seq_recent_log_status="PASS"
fi

prometheus_health_status="UNKNOWN"
if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
  default_prometheus_url="http://host.docker.internal:9091"
else
  default_prometheus_url=""
fi
prometheus_url="${PROMETHEUS_URL:-$default_prometheus_url}"
if [ -n "$prometheus_url" ]; then
  if curl --fail --silent --show-error "${prometheus_url%/}/-/ready" >/dev/null; then
    prometheus_health_status="PASS"
  else
    prometheus_health_status="FAIL"
  fi
fi

jq -n \
  --arg commitSha "$commit_sha" \
  --arg environment "${environment^^}" \
  --arg provider "rancher-desktop" \
  --arg namespace "$namespace" \
  --arg siteHealthUrl "${site_url%/}/health" \
  --arg apiHealthUrl "${api_url%/}/health" \
  --arg siteImageDigest "$site_digest" \
  --arg apiImageDigest "$api_digest" \
  --arg siteHealthStatus "$site_health_status" \
  --arg apiHealthStatus "$api_health_status" \
  --arg prometheusHealthStatus "$prometheus_health_status" \
  --arg seqRecentLogStatus "$seq_recent_log_status" \
  --arg checkedAtUtc "$checked_at_utc" \
  '{
    commitSha: $commitSha,
    environment: $environment,
    provider: $provider,
    namespace: $namespace,
    siteHealthUrl: $siteHealthUrl,
    apiHealthUrl: $apiHealthUrl,
    siteImageDigest: $siteImageDigest,
    apiImageDigest: $apiImageDigest,
    siteHealthStatus: $siteHealthStatus,
    apiHealthStatus: $apiHealthStatus,
    prometheusHealthStatus: $prometheusHealthStatus,
    seqRecentLogStatus: $seqRecentLogStatus,
    checkedAtUtc: $checkedAtUtc
  }' > "$output_dir/monitoring-summary.json"

cat "$output_dir/monitoring-summary.json"

if [ "$site_health_status" != "PASS" ] || [ "$api_health_status" != "PASS" ]; then
  echo "site and api health checks must pass for Rancher observability evidence." >&2
  exit 1
fi

if [ "$prometheus_health_status" = "FAIL" ]; then
  echo "Prometheus readiness check failed." >&2
  exit 1
fi
