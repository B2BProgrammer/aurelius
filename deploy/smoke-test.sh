#!/usr/bin/env bash
# End-to-end check of a running Aurelius system, through the web app's front door.
# Used by CI (docker compose) and CD (Kubernetes, via port-forward).
#
#   BASE=http://127.0.0.1:8080 DEV_LOGIN_PASSWORD=... ./deploy/smoke-test.sh
#
# 1. the web app answers                       (/healthz)
# 2. sign in works                             (/v1/auth/login -> token)
# 3. the Conductor can reach all 10 agents     (/v1/agents: every status "up")
# 4. a real question gets an answer            (/v1/chat)
# Without DEV_LOGIN_PASSWORD (e.g. production, where dev sign-in is off) only step 1 runs.
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8080}"
USERNAME="${SMOKE_USER:-advisor}"

step() { printf '\n== %s\n' "$1"; }
fail() { printf 'FAILED: %s\n' "$1" >&2; exit 1; }

step "Web app is up"
curl -fsS --retry 10 --retry-delay 3 --retry-all-errors "$BASE/healthz" || fail "web app not reachable at $BASE"

if [ -z "${DEV_LOGIN_PASSWORD:-}" ]; then
  echo "DEV_LOGIN_PASSWORD not set: skipping sign-in and chat checks."
  exit 0
fi

step "Sign in"
login=$(curl -fsS -X POST "$BASE/v1/auth/login" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg u "$USERNAME" --arg p "$DEV_LOGIN_PASSWORD" '{username: $u, password: $p}')") \
  || fail "sign-in failed"
token=$(jq -r .access_token <<<"$login")
[ -n "$token" ] && [ "$token" != "null" ] || fail "no access_token in sign-in response"
echo "signed in as $USERNAME"

step "All agents reachable from the Conductor"
# Java agents can take a little longer to start: retry for up to 2 minutes
for attempt in $(seq 1 24); do
  agents=$(curl -fsS "$BASE/v1/agents" -H "Authorization: Bearer $token") || fail "/v1/agents failed"
  not_up=$(jq '[.[] | select(.status != "up")] | length' <<<"$agents")
  [ "$not_up" -eq 0 ] && break
  echo "attempt $attempt: $not_up agent(s) not up yet, waiting..."
  sleep 5
done
jq -r '.[] | "\(.status)\t\(.codename // .name)"' <<<"$agents"
[ "$not_up" -eq 0 ] || fail "$not_up agent(s) not up"

step "Ask a question"
answer=$(curl -fsS -X POST "$BASE/v1/chat" -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
  -d '{"message": "Give me a portfolio overview for this household", "client_id": "patel-001"}') \
  || fail "/v1/chat failed"
text=$(jq -r .answer <<<"$answer")
[ -n "$text" ] && [ "$text" != "null" ] || fail "empty answer"
printf '%s\n' "$text" | head -c 400; echo
echo "steps run: $(jq '.steps | length' <<<"$answer"), trace: $(jq -r .trace_id <<<"$answer")"

printf '\nSMOKE TEST PASSED\n'
