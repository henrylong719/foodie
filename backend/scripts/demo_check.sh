#!/usr/bin/env bash
#
# Pre-demo verification. Run from backend/:
#   bash ./scripts/demo_check.sh
#
# Verifies the things that actually break a Foodie demo on stage:
#   - backend is up and Mongo is connected
#   - Vapi is configured for a live call (not dry-run)
#   - the seeded demo customer is callable and has the canonical history
#   - the configured webhook URL actually reaches this backend
#
# Exits non-zero if any check fails so it can gate `bun run dev` in scripts.

set -uo pipefail

cd "$(dirname "$0")/.."

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
DEMO_PHONE="+12176373205"
DEMO_NAME="Henry Long"
DEMO_SUBCATEGORIES=("Chips" "Ice Cream" "Soft Drink")

if [[ -t 1 ]]; then
  RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'
  DIM=$'\033[2m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
else
  RED=""; GREEN=""; YELLOW=""; DIM=""; BOLD=""; RESET=""
fi

pass_count=0
fail_count=0
warn_count=0

pass() { echo "  ${GREEN}✓${RESET} $1"; pass_count=$((pass_count + 1)); }
fail() { echo "  ${RED}✗${RESET} $1"; fail_count=$((fail_count + 1)); }
warn() { echo "  ${YELLOW}!${RESET} $1"; warn_count=$((warn_count + 1)); }
section() { echo; echo "${BOLD}── $1 ──${RESET}"; }

# Load backend/.env so VAPI_* and CALLING_HOURS_OVERRIDE are readable here.
if [[ -f .env ]]; then
  set -o allexport
  # shellcheck disable=SC1091
  source .env
  set +o allexport
fi

# ---------------------------------------------------------------------------
section "Backend health"
# ---------------------------------------------------------------------------

health_body=$(curl -fsS --max-time 3 "$BACKEND_URL/health" 2>/dev/null || true)
if [[ -z "$health_body" ]]; then
  fail "Backend not responding at $BACKEND_URL"
  echo "    Start it with: uv run uvicorn app.main:app --reload"
  echo
  echo "${RED}Aborting — nothing else to check without the backend.${RESET}"
  exit 1
fi

status=$(printf '%s' "$health_body" | python3 -c \
  "import json,sys; print(json.load(sys.stdin).get('status',''))")
db_ok=$(printf '%s' "$health_body" | python3 -c \
  "import json,sys; print(json.load(sys.stdin).get('database', False))")

if [[ "$status" == "ok" ]]; then
  pass "Backend healthy ($BACKEND_URL)"
else
  fail "Backend status is '$status' — expected 'ok'"
fi

if [[ "$db_ok" == "True" ]]; then
  pass "MongoDB connected"
else
  fail "MongoDB not connected — check MONGODB_URI"
fi

# ---------------------------------------------------------------------------
section "Vapi configuration"
# ---------------------------------------------------------------------------

if [[ -z "${VAPI_API_KEY:-}" ]]; then
  fail "VAPI_API_KEY is empty — backend is in DRY-RUN; no real call will happen"
else
  pass "VAPI_API_KEY set"
fi

if [[ -z "${VAPI_ASSISTANT_ID:-}" ]]; then
  fail "VAPI_ASSISTANT_ID is empty — live calls will be refused"
else
  pass "VAPI_ASSISTANT_ID set"
fi

if [[ -z "${VAPI_PHONE_NUMBER_ID:-}" ]]; then
  fail "VAPI_PHONE_NUMBER_ID is empty — live calls will be refused"
else
  pass "VAPI_PHONE_NUMBER_ID set"
fi

# ---------------------------------------------------------------------------
section "Demo customer"
# ---------------------------------------------------------------------------

customers_body=$(curl -fsS --max-time 3 "$BACKEND_URL/customers?limit=500" 2>/dev/null || true)
demo_id=""
if [[ -z "$customers_body" ]]; then
  fail "Could not list customers"
else
  read -r demo_id demo_dnc <<<"$(printf '%s' "$customers_body" | DEMO_PHONE="$DEMO_PHONE" python3 -c '
import json, os, sys
data = json.load(sys.stdin)
for c in data.get("customers", []):
    if c.get("phone") == os.environ["DEMO_PHONE"]:
        print(c.get("_id", ""), c.get("do_not_call", False))
        sys.exit()
print("", "")
')"

  if [[ -z "$demo_id" ]]; then
    fail "$DEMO_NAME ($DEMO_PHONE) not found — run 'uv run seed.py'"
  elif [[ "$demo_dnc" == "True" ]]; then
    fail "$DEMO_NAME is marked do-not-call — reseed: 'uv run seed.py'"
  else
    pass "$DEMO_NAME ($DEMO_PHONE) is callable"
  fi
fi

# ---------------------------------------------------------------------------
section "Demo history coverage"
# ---------------------------------------------------------------------------

if [[ -n "$demo_id" ]]; then
  history_body=$(curl -fsS --max-time 3 "$BACKEND_URL/customers/$demo_id/history?limit=100" 2>/dev/null || true)
  if [[ -z "$history_body" ]]; then
    fail "Could not fetch demo customer's history"
  else
    subs_csv=$(printf '%s\n' "${DEMO_SUBCATEGORIES[@]}" | paste -sd, -)
    missing=$(printf '%s' "$history_body" | SUBS="$subs_csv" python3 -c '
import json, os, sys
data = json.load(sys.stdin)
wanted = set(os.environ["SUBS"].split(","))
seen = {i.get("subcategory") for i in data.get("items", [])}
print(",".join(sorted(wanted - seen)))
')
    if [[ -z "$missing" ]]; then
      pass "history covers Chips, Ice Cream, Soft Drink"
    else
      warn "history missing: $missing — reseed for the canonical demo paths"
    fi
  fi
fi

# ---------------------------------------------------------------------------
section "Webhook reachability"
# ---------------------------------------------------------------------------

if [[ -z "${VAPI_WEBHOOK_URL:-}" ]]; then
  warn "VAPI_WEBHOOK_URL not set — relying on the assistant's saved Server URL in Vapi"
  warn "  cannot verify the tunnel from here; double-check the Vapi assistant config"
else
  echo "  ${DIM}probing $VAPI_WEBHOOK_URL${RESET}"
  probe=$(curl -fsS --max-time 5 -X POST "$VAPI_WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d '{"message":{"type":"demo-check","call":{"id":"demo-check"}}}' \
    2>/dev/null || true)
  if [[ "$probe" == *"received"* ]]; then
    pass "webhook reachable: $VAPI_WEBHOOK_URL"
  else
    fail "webhook unreachable — tunnel may be down or URL stale"
    echo "    Restart the tunnel and update the Vapi assistant Server URL"
  fi
fi

# ---------------------------------------------------------------------------
section "Compliance gate"
# ---------------------------------------------------------------------------

if [[ "${CALLING_HOURS_OVERRIDE:-false}" == "true" ]]; then
  warn "CALLING_HOURS_OVERRIDE=true — calling-hours gate is BYPASSED (fine for demo)"
else
  pass "CALLING_HOURS_OVERRIDE off — compliance gate is live"
fi

# ---------------------------------------------------------------------------
echo
if (( fail_count > 0 )); then
  echo "${RED}${BOLD}${fail_count} check(s) failed.${RESET} Fix before demoing."
  exit 1
fi
if (( warn_count > 0 )); then
  echo "${YELLOW}${warn_count} warning(s).${RESET} Demo can proceed."
fi
echo "${GREEN}${BOLD}Ready to demo.${RESET} (${pass_count} checks passed)"
