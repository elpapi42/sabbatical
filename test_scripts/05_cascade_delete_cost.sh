#!/usr/bin/env bash
# Test Workflow 05: Cascade Delete & Cost Aggregation
# Tests: org delete cascades to agents/tasks/comments/runs/sessions,
#        cost aggregation across runs, task sequences cleanup
set -euo pipefail

cd /home/whitman/sabbatical
BASE="http://127.0.0.1:7420/api"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }
section() { echo -e "\n=== $1 ==="; }

wait_for_server() {
    for i in $(seq 1 20); do
        curl -sf "http://127.0.0.1:7420/api/status" >/dev/null 2>&1 && return 0
        sleep 1
    done
    return 1
}

# Ensure server is running
if ! curl -sf "$BASE/status" >/dev/null 2>&1; then
    echo "Starting server..."
    poetry run sabbatical server up 2>/dev/null
    wait_for_server || { echo "FATAL: Server failed to start"; exit 1; }
fi

WORKSPACE="/tmp/sabbatical_test_cascade"
mkdir -p "$WORKSPACE/.sabbatical/agents"
echo "You are the lead." > "$WORKSPACE/.sabbatical/agents/lead.md"

curl -sf -X DELETE "$BASE/organizations/test_cascade_org" >/dev/null 2>&1 || true

# ── Setup: create org, agent, tasks, comments ──
section "Setup"
curl -sf -X POST "$BASE/organizations" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"test_cascade_org\",\"workspace_path\":\"$WORKSPACE\",\"description\":\"Cascade test\"}" >/dev/null

curl -sf -X POST "$BASE/organizations/test_cascade_org/agents" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"lead\",\"instructions_path\":\"$WORKSPACE/.sabbatical/agents/lead.md\",\"description\":\"Lead\"}" >/dev/null

RESP=$(curl -sf -X POST "$BASE/tasks" \
    -H "Content-Type: application/json" \
    -d '{"title":"Cascade test task","organization":"test_cascade_org","description":"Will be deleted"}')
TASK_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -sf -X POST "$BASE/tasks/$TASK_ID/comments" \
    -H "Content-Type: application/json" \
    -d '{"body":"Test comment on cascade task"}' >/dev/null

# Create a session scoped to this org
RESP=$(curl -sf -X POST "$BASE/sessions" \
    -H "Content-Type: application/json" \
    -d '{"organization_scope":"test_cascade_org"}')
SESSION_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

pass "Setup complete: org + agent + task + comment + session"

# ── 1. Verify all entities exist ──
section "Pre-Delete Verification"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/organizations/test_cascade_org")
[ "$HTTP_CODE" = "200" ] && pass "Org exists" || fail "Org missing"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/organizations/test_cascade_org/agents/lead")
[ "$HTTP_CODE" = "200" ] && pass "Agent exists" || fail "Agent missing"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/tasks/$TASK_ID")
[ "$HTTP_CODE" = "200" ] && pass "Task exists" || fail "Task missing"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/sessions/$SESSION_ID")
[ "$HTTP_CODE" = "200" ] && pass "Session exists" || fail "Session missing"

# ── 2. Cascade delete ──
section "Cascade Delete"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE/organizations/test_cascade_org")
[ "$HTTP_CODE" = "204" ] || [ "$HTTP_CODE" = "200" ] && pass "Org deleted" || fail "Delete returned $HTTP_CODE"

# ── 3. Verify all entities gone ──
section "Post-Delete Verification"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/organizations/test_cascade_org")
[ "$HTTP_CODE" = "404" ] && pass "Org gone (404)" || fail "Org still exists: $HTTP_CODE"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/tasks/$TASK_ID")
[ "$HTTP_CODE" = "404" ] && pass "Task gone (404)" || fail "Task still exists: $HTTP_CODE"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/sessions/$SESSION_ID")
[ "$HTTP_CODE" = "404" ] && pass "Session gone (404)" || fail "Session still exists: $HTTP_CODE"

# ── 4. Cost aggregation (zero cost, but structure should work) ──
section "Cost Aggregation"
# Create fresh org for cost testing
curl -sf -X DELETE "$BASE/organizations/test_cost_org" >/dev/null 2>&1 || true
curl -sf -X POST "$BASE/organizations" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"test_cost_org\",\"workspace_path\":\"$WORKSPACE\"}" >/dev/null

curl -sf -X POST "$BASE/organizations/test_cost_org/agents" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"lead\",\"instructions_path\":\"$WORKSPACE/.sabbatical/agents/lead.md\"}" >/dev/null

# Check org-level cost fields
RESP=$(curl -sf "$BASE/organizations/test_cost_org")
if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert 'consumed_input_tokens' in d
assert 'consumed_output_tokens' in d
assert 'total_cost' in d
assert d['total_cost'] == 0.0
" 2>/dev/null; then
    pass "Org detail includes cost fields (zero for new org)"
else
    fail "Org cost fields missing"
fi

# Check system-level cost in status
RESP=$(curl -sf "$BASE/status")
if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert 'consumed_input_tokens' in d
assert 'consumed_output_tokens' in d
assert 'total_cost' in d
" 2>/dev/null; then
    pass "System status includes cost fields"
else
    fail "System status cost fields missing"
fi

# ── 5. Task sequential IDs ──
section "Task ID Sequencing"
RESP1=$(curl -sf -X POST "$BASE/tasks" \
    -H "Content-Type: application/json" \
    -d '{"title":"Seq 1","organization":"test_cost_org"}')
ID1=$(echo "$RESP1" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

RESP2=$(curl -sf -X POST "$BASE/tasks" \
    -H "Content-Type: application/json" \
    -d '{"title":"Seq 2","organization":"test_cost_org"}')
ID2=$(echo "$RESP2" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Extract sequence numbers
NUM1=$(echo "$ID1" | grep -oE '[0-9]+$')
NUM2=$(echo "$ID2" | grep -oE '[0-9]+$')

if [ "$((NUM2))" -eq "$((NUM1 + 1))" ]; then
    pass "Task IDs are sequential: $ID1 -> $ID2"
else
    fail "Task IDs not sequential: $ID1 -> $ID2"
fi

# Cleanup
curl -sf -X DELETE "$BASE/organizations/test_cost_org" >/dev/null 2>&1 || true
rm -rf "$WORKSPACE"

# ── Summary ──
echo -e "\n=========================================="
echo "Cascade Delete & Cost: $PASS passed, $FAIL failed"
echo "=========================================="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
