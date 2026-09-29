#!/usr/bin/env bash
set -euo pipefail

# Runs against an already-started local Compose stack. The checks deliberately
# exercise the safe demo path and do not require provider or LLM credentials.
compose=(docker compose)
tmpdir="$(mktemp -d)"
cookiejar="$tmpdir/cookies.txt"
trap 'rm -rf "$tmpdir"' EXIT

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
if payload.get("status") != "success":
    sys.exit(1)
data = payload.get("data", {})
if data.get("resultType") != "vector":
    sys.exit(1)
if not any(
    item.get("metric", {}).get("job") == sys.argv[1]
    and item.get("value", [None, None])[1] == "1"
    for item in data.get("result", [])
):
    sys.exit(1)
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

# Exercise the same Next.js session/proxy path used by the browser UI.
frontend_login="$(curl --fail --silent --show-error \
  --cookie-jar "$cookiejar" \
  --dump-header "$tmpdir/login.headers" \
  -F "username=demo@cloudpulse.local" \
  -F "password=DemoPass123!" \
  http://localhost:3005/api/auth/login)"
if [[ -z "$frontend_login" ]]; then
  echo "Frontend login returned an empty body; response status and headers:" >&2
  sed -E '/^[Ss]et-[Cc]ookie:/d' "$tmpdir/login.headers" >&2
  exit 1
fi
python -c '
import json, sys
login = json.load(sys.stdin)
assert login["token_type"] == "bearer", login
' <<<"$frontend_login"
echo "Frontend login response validated"

me="$(curl --fail --silent --show-error --cookie "$cookiejar" http://localhost:3005/api/auth/me)"
python -c '
import json, sys
profile = json.load(sys.stdin)
assert profile["email"] == "demo@cloudpulse.local", profile
assert profile.get("organization_id"), profile
' <<<"$me"
echo "Authenticated profile response validated"

summary="$(curl --fail --silent --show-error --cookie "$cookiejar"   "http://localhost:3005/api/cost/costs/summary?days=30")"
python -c '
import json, sys
summary = json.load(sys.stdin)
assert summary["currency"] == "USD", summary
assert summary["total_cost"] is not None, summary
assert "credentials" not in summary, summary
' <<<"$summary"
echo "Cost summary response validated"

ml_status="$(curl --fail --silent --show-error --cookie "$cookiejar" http://localhost:3005/api/ml/ml/status)"
python -c '
import json, sys
status = json.load(sys.stdin)
assert "predictor_fitted" in status, status
assert "detector_fitted" in status, status
' <<<"$ml_status"
echo "ML status response validated"

# Public health remains public; live-provider preflight and ML status do not.
preflight_status="$(curl --silent --output /dev/null --write-out "%{http_code}" http://localhost:8001/api/v1/health/preflight/gcp)"
test "$preflight_status" = "401"
ml_unauth_status="$(curl --silent --output /dev/null --write-out "%{http_code}" http://localhost:8002/api/v1/ml/status)"
test "$ml_unauth_status" = "401"

# Exercise the actual frontend -> cost API -> RabbitMQ -> worker -> database path.
accounts="$(curl --fail --silent --show-error --cookie "$cookiejar" http://localhost:3005/api/cost/accounts/)"
account_id="$(python -c 'import json, sys; print(json.load(sys.stdin)["items"][0]["id"])' <<<"$accounts")"
csrf="$(awk '$6 == "cloudpulse_csrf_token" { print $7; exit }' "$cookiejar")"
test -n "$csrf"
sync_response="$(curl --fail --silent --show-error --cookie "$cookiejar"   -H "X-CSRF-Token: $csrf"   -X POST "http://localhost:3005/api/cost/accounts/$account_id/sync")"
task_id="$(python -c 'import json, sys; print(json.load(sys.stdin)["task_id"])' <<<"$sync_response")"

task_status="queued"
for attempt in $(seq 1 60); do
  task_json="$(curl --fail --silent --show-error --cookie "$cookiejar"     "http://localhost:3005/api/cost/accounts/$account_id/sync/$task_id")"
  task_status="$(python -c 'import json, sys; print(json.load(sys.stdin)["status"])' <<<"$task_json")"
  if [ "$task_status" = "succeeded" ]; then
    break
  fi
  if [ "$task_status" = "failed" ]; then
    echo "Sync task failed: $task_json" >&2
    exit 1
  fi
  sleep 1
done
test "$task_status" = "succeeded"

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
