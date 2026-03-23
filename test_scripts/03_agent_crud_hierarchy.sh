#!/usr/bin/env bash
# Test Workflow 03: Agent CRUD & Hierarchy
# Tests: add, list, view, edit, remove (soft-delete), boss validation,
#        subordinate promotion, hierarchy tree, include_removed
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

# Setup: create org + instructions files
WORKSPACE="/tmp/sabbatical_test_agents"
mkdir -p "$WORKSPACE/.sabbatical/agents"
echo "You are the lead engineer. Coordinate work across the team." > "$WORKSPACE/.sabbatical/agents/lead.md"
echo "You are a frontend developer specializing in React." > "$WORKSPACE/.sabbatical/agents/frontend_dev.md"
echo "You are a backend developer specializing in APIs." > "$WORKSPACE/.sabbatical/agents/backend_dev.md"

curl -sf -X DELETE "$BASE/organizations/test_agent_org" >/dev/null 2>&1 || true
curl -sf -X POST "$BASE/organizations" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"test_agent_org\",\"workspace_path\":\"$WORKSPACE\"}" >/dev/null

# ── 1. Add root agent ──
section "Add Root Agent"
RESP=$(curl -sf -X POST "$BASE/organizations/test_agent_org/agents" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"lead\",\"instructions_path\":\"$WORKSPACE/.sabbatical/agents/lead.md\",\"description\":\"Lead engineer\"}")

if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['name']=='lead'; assert d['boss'] is None" 2>/dev/null; then
    pass "Root agent created with no boss"
else
    fail "Root agent creation failed: $RESP"
fi

# ── 2. Add subordinate agents ──
section "Add Subordinate Agents"
RESP=$(curl -sf -X POST "$BASE/organizations/test_agent_org/agents" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"frontend_dev\",\"instructions_path\":\"$WORKSPACE/.sabbatical/agents/frontend_dev.md\",\"description\":\"React frontend dev\",\"boss\":\"lead\"}")

if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['boss']=='lead'" 2>/dev/null; then
    pass "Subordinate frontend_dev created with boss=lead"
else
    fail "Subordinate creation failed: $RESP"
fi

curl -sf -X POST "$BASE/organizations/test_agent_org/agents" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"backend_dev\",\"instructions_path\":\"$WORKSPACE/.sabbatical/agents/backend_dev.md\",\"description\":\"API backend dev\",\"boss\":\"lead\"}" >/dev/null
pass "Subordinate backend_dev created"

# ── 3. Duplicate name rejected ──
section "Duplicate Agent Validation"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/organizations/test_agent_org/agents" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"lead\",\"instructions_path\":\"$WORKSPACE/.sabbatical/agents/lead.md\"}")

if [ "$HTTP_CODE" = "409" ]; then
    pass "Duplicate agent name returns 409"
else
    fail "Duplicate agent returned $HTTP_CODE (expected 409)"
fi

# ── 4. Non-existent boss rejected ──
section "Invalid Boss Validation"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/organizations/test_agent_org/agents" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"orphan\",\"instructions_path\":\"$WORKSPACE/.sabbatical/agents/lead.md\",\"boss\":\"ghost_agent\"}")

if [ "$HTTP_CODE" = "404" ]; then
    pass "Non-existent boss returns 404"
else
    fail "Non-existent boss returned $HTTP_CODE (expected 404)"
fi

# ── 5. List agents ──
section "List Agents"
RESP=$(curl -sf "$BASE/organizations/test_agent_org/agents")

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
names = [a['name'] for a in d['agents']]
assert 'lead' in names
assert 'frontend_dev' in names
assert 'backend_dev' in names
assert len(names) == 3
" 2>/dev/null; then
    pass "List returns all 3 agents"
else
    fail "List response unexpected: $RESP"
fi

# ── 6. View agent detail ──
section "View Agent Detail"
RESP=$(curl -sf "$BASE/organizations/test_agent_org/agents/lead")

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['name']=='lead'
assert 'instructions_content' in d
assert 'subordinates' in d
sub_names = [s['name'] for s in d['subordinates']]
assert 'frontend_dev' in sub_names
assert 'backend_dev' in sub_names
" 2>/dev/null; then
    pass "View shows instructions_content and subordinates"
else
    fail "View response unexpected: $RESP"
fi

# ── 7. Org view shows hierarchy tree ──
section "Organization Hierarchy Tree"
RESP=$(curl -sf "$BASE/organizations/test_agent_org")

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
# Root should be lead with subordinates
assert len(d['agents']) == 1  # Only root agents at top level
root = d['agents'][0]
assert root['name'] == 'lead'
assert len(root['subordinates']) == 2
" 2>/dev/null; then
    pass "Org view shows nested hierarchy (lead -> [frontend_dev, backend_dev])"
else
    fail "Org hierarchy unexpected: $RESP"
fi

# ── 8. Edit agent ──
section "Edit Agent"
RESP=$(curl -sf -X PATCH "$BASE/organizations/test_agent_org/agents/frontend_dev" \
    -H "Content-Type: application/json" \
    -d '{"description":"Senior React frontend dev","max_iterations":100}')

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['description']=='Senior React frontend dev'
assert d['max_iterations']==100
" 2>/dev/null; then
    pass "Agent edit updates description and max_iterations"
else
    fail "Agent edit response unexpected: $RESP"
fi

# ── 9. Soft-delete agent with subordinate promotion ──
section "Soft Delete & Subordinate Promotion"
RESP=$(curl -sf -X DELETE "$BASE/organizations/test_agent_org/agents/lead")

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['removed']=='lead'
" 2>/dev/null; then
    pass "Lead agent soft-deleted"
else
    fail "Soft delete response unexpected: $RESP"
fi

# Check subordinates promoted to root
RESP=$(curl -sf "$BASE/organizations/test_agent_org/agents/frontend_dev")
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['boss'] is None" 2>/dev/null; then
    pass "frontend_dev promoted to root (boss=null)"
else
    fail "frontend_dev not promoted: $RESP"
fi

# ── 10. Removed agent excluded from list ──
section "Include Removed Filter"
RESP=$(curl -sf "$BASE/organizations/test_agent_org/agents")
if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
names = [a['name'] for a in d['agents']]
assert 'lead' not in names
" 2>/dev/null; then
    pass "Removed agent excluded from default list"
else
    fail "Removed agent still in list: $RESP"
fi

RESP=$(curl -sf "$BASE/organizations/test_agent_org/agents?include_removed=true")
if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
names = [a['name'] for a in d['agents']]
assert 'lead' in names
lead = [a for a in d['agents'] if a['name']=='lead'][0]
assert lead['is_removed'] == True
" 2>/dev/null; then
    pass "Removed agent visible with include_removed=true"
else
    fail "include_removed filter not working: $RESP"
fi

# Cleanup
curl -sf -X DELETE "$BASE/organizations/test_agent_org" >/dev/null 2>&1 || true
rm -rf "$WORKSPACE"

# ── Summary ──
echo -e "\n=========================================="
echo "Agent CRUD & Hierarchy: $PASS passed, $FAIL failed"
echo "=========================================="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
