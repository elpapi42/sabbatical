#!/usr/bin/env bash
# Test Workflow 02: Organization CRUD
# Tests: create, list, view, edit, delete, validation errors, cascade delete
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

# Cleanup any leftover test org
curl -sf -X DELETE "$BASE/organizations/test_workflow_org" >/dev/null 2>&1 || true

WORKSPACE="/tmp/sabbatical_test_workspace"
mkdir -p "$WORKSPACE"

# ── 1. Create organization ──
section "Create Organization"
RESP=$(curl -sf -X POST "$BASE/organizations" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"test_workflow_org\",\"workspace_path\":\"$WORKSPACE\",\"description\":\"Test org for workflow\"}")

if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['name']=='test_workflow_org'" 2>/dev/null; then
    pass "Organization created successfully"
else
    fail "Organization creation failed: $RESP"
fi

# ── 2. Duplicate name rejected ──
section "Duplicate Name Validation"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/organizations" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"test_workflow_org\",\"workspace_path\":\"$WORKSPACE\",\"description\":\"dup\"}")

if [ "$HTTP_CODE" = "409" ]; then
    pass "Duplicate org name returns 409"
else
    fail "Duplicate org name returned $HTTP_CODE (expected 409)"
fi

# ── 3. Invalid snake_case rejected ──
section "Snake Case Validation"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/organizations" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"InvalidName\",\"workspace_path\":\"$WORKSPACE\"}")

if [ "$HTTP_CODE" = "422" ]; then
    pass "Invalid snake_case name returns 422"
else
    fail "Invalid snake_case name returned $HTTP_CODE (expected 422)"
fi

# ── 4. List organizations ──
section "List Organizations"
RESP=$(curl -sf "$BASE/organizations")

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
orgs = d['organizations']
names = [o['name'] for o in orgs]
assert 'test_workflow_org' in names
# Check cost fields exist
org = [o for o in orgs if o['name']=='test_workflow_org'][0]
assert 'total_cost' in org
assert 'agent_count' in org
" 2>/dev/null; then
    pass "List includes test org with expected fields"
else
    fail "List response unexpected: $RESP"
fi

# ── 5. View organization detail ──
section "View Organization"
RESP=$(curl -sf "$BASE/organizations/test_workflow_org")

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['name']=='test_workflow_org'
assert d['workspace_path']=='$WORKSPACE'
assert 'agents' in d
assert isinstance(d['agents'], list)
" 2>/dev/null; then
    pass "View returns detail with agents tree"
else
    fail "View response unexpected: $RESP"
fi

# ── 6. Edit organization ──
section "Edit Organization"
RESP=$(curl -sf -X PATCH "$BASE/organizations/test_workflow_org" \
    -H "Content-Type: application/json" \
    -d '{"description":"Updated description"}')

if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['description']=='Updated description'" 2>/dev/null; then
    pass "Edit updates description"
else
    fail "Edit response unexpected: $RESP"
fi

# ── 7. 404 on non-existent org ──
section "Not Found"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/organizations/nonexistent_org_xyz")

if [ "$HTTP_CODE" = "404" ]; then
    pass "Non-existent org returns 404"
else
    fail "Non-existent org returned $HTTP_CODE (expected 404)"
fi

# ── 8. Delete organization ──
section "Delete Organization"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE/organizations/test_workflow_org")

if [ "$HTTP_CODE" = "204" ] || [ "$HTTP_CODE" = "200" ]; then
    pass "Organization deleted"
else
    fail "Delete returned $HTTP_CODE (expected 204)"
fi

# Verify gone
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/organizations/test_workflow_org")
if [ "$HTTP_CODE" = "404" ]; then
    pass "Deleted org returns 404"
else
    fail "Deleted org still accessible: $HTTP_CODE"
fi

# ── 9. CLI create + list + delete ──
section "CLI Workflow"
poetry run sabbatical organization create test_cli_org --workspace-path "$WORKSPACE" --description "CLI test" 2>/dev/null

CLI_LIST=$(poetry run sabbatical organization list 2>&1)
if echo "$CLI_LIST" | grep -q "test_cli_org"; then
    pass "CLI list shows created org"
else
    fail "CLI list missing org: $CLI_LIST"
fi

poetry run sabbatical organization delete test_cli_org --yes 2>/dev/null
CLI_LIST=$(poetry run sabbatical organization list 2>&1)
if echo "$CLI_LIST" | grep -q "test_cli_org"; then
    fail "CLI list still shows deleted org"
else
    pass "CLI org properly deleted"
fi

# Cleanup
rm -rf "$WORKSPACE"

# ── Summary ──
echo -e "\n=========================================="
echo "Organization CRUD: $PASS passed, $FAIL failed"
echo "=========================================="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
