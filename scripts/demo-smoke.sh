#!/usr/bin/env bash
set -euo pipefail

# Runs against an already-started local Compose stack. The checks deliberately
# exercise the safe demo path and do not require provider or LLM credentials.
compose=(docker compose)

wait_for() {
  local url="$1"
  local label="$2"
  local deadline=$((SECONDS + 120))
  until curl --fail --silent --show-error "$url" >/dev/null; do
    if (( SECONDS >= deadline )); then
      echo "Timed out waiting for ${label}: ${url}" >&2
      "${compose[@]}" ps >&2 || true
      "${compose[@]}" logs --tail=100 cost-service ml-service frontend >&2 || true
      exit 1
    fi
    sleep 2
  done
}

wait_for_prometheus_target() {
  local job="$1"
  local deadline=$((SECONDS + 120))
  local query="up{job=\"${job}\"}"

  # `/-/ready` only proves the Prometheus HTTP server is accepting requests.
  # This additionally proves that the configured target was scraped and is up.
  until curl --fail --silent --show-error --get \
    --data-urlencode "query=${query}" \
    http://localhost:9090/api/v1/query \
    | python -c '
import json
import sys

payload = json.load(sys.stdin)
assert payload["status"] == "success", payload
data = payload["data"]
assert data["resultType"] == "vector", data
assert any(
    item.get("metric", {}).get("job") == sys.argv[1]
    and item.get("value", [None, None])[1] == "1"
    for item in data["result"]
), data
' "${job}"; do
    if (( SECONDS >= deadline )); then
      echo "Timed out waiting for Prometheus to scrape ${job}" >&2
      "${compose[@]}" ps >&2 || true
      "${compose[@]}" logs --tail=100 prometheus "${job}" >&2 || true
      exit 1
    fi
    sleep 2
  done
}

wait_for "http://localhost:8001/health" "cost-service"
wait_for "http://localhost:8002/health" "ml-service"
wait_for "http://localhost:3005" "frontend"
wait_for "http://localhost:9090/-/ready" "Prometheus"
wait_for "http://localhost:9093/-/ready" "Alertmanager"

runtime="$(curl --fail --silent http://localhost:8001/api/v1/health/runtime)"
python -c '
import json, sys
runtime = json.loads(sys.stdin.read())
assert runtime["cloud_sync_mode"] == "demo", runtime
assert runtime["allow_live_cloud_sync"] is False, runtime
' <<<"${runtime}"

# Confirm that Prometheus can be queried and that both backend scrape targets
# have returned a non-empty `up == 1` vector.
wait_for_prometheus_target "cost-service"
wait_for_prometheus_target "ml-service"

echo "CloudPulse demo smoke checks passed."
