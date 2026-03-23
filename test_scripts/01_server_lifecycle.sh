#!/usr/bin/env bash
# Test Workflow 01: Server Lifecycle
# Tests: server up, status, down, idempotency, stale PID recovery
set -euo pipefail

cd /home/whitman/sabbatical
BASE="http://127.0.0.1:7420"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }
section() { echo -e "\n=== $1 ==="; }

wait_for_server() {
    for i in $(seq 1 20); do
        curl -sf "$BASE/api/status" >/dev/null 2>&1 && return 0
        sleep 1
    done
    return 1
}

wait_for_shutdown() {
    for i in $(seq 1 10); do
        curl -sf "$BASE/api/status" >/dev/null 2>&1 || return 0
        sleep 1
    done
    return 1
}

cleanup() {
    curl -s -X POST "$BASE/api/shutdown" >/dev/null 2>&1 || true
    sleep 2
    [ -f ~/.sabbatical/server.pid ] && kill "$(cat ~/.sabbatical/server.pid)" 2>/dev/null || true
    rm -f ~/.sabbatical/server.pid
}
trap cleanup EXIT

# ── 1. Start server ──
section "Server Start"
poetry run sabbatical server up 2>/dev/null

if wait_for_server; then
    pass "Server responds to /api/status after startup"
else
    fail "Server not responding after startup"
fi

# ── 2. Status endpoint returns expected shape ──
section "Status Endpoint"
STATUS=$(curl -sf "$BASE/api/status")

if echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['server']=='running'" 2>/dev/null; then
    pass "Status reports server=running"
else
    fail "Status does not report server=running"
fi

if echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'tasks' in d; assert 'active_workers' in d; assert 'max_concurrency' in d" 2>/dev/null; then
    pass "Status contains tasks, active_workers, max_concurrency fields"
else
    fail "Status missing expected fields"
fi

# ── 3. Double start is rejected ──
section "Double Start Prevention"
OUTPUT=$(poetry run sabbatical server up 2>&1 || true)
if echo "$OUTPUT" | grep -qi "already running"; then
    pass "Double start is rejected with 'already running' message"
else
    fail "Double start was not properly rejected: $OUTPUT"
fi

# ── 4. CLI status command ──
section "CLI Status"
CLI_STATUS=$(poetry run sabbatical server status 2>&1 || true)
if echo "$CLI_STATUS" | grep -qi "running\|workers\|tasks"; then
    pass "CLI 'server status' returns meaningful output"
else
    fail "CLI 'server status' output unexpected: $CLI_STATUS"
fi

# ── 5. Graceful shutdown ──
section "Graceful Shutdown"
poetry run sabbatical server down 2>/dev/null

if wait_for_shutdown; then
    pass "Server stopped responding after shutdown"
else
    fail "Server still responding after shutdown"
fi

if [ ! -f ~/.sabbatical/server.pid ]; then
    pass "PID file cleaned up after shutdown"
else
    fail "PID file still exists after shutdown"
fi

# ── 6. Stale PID recovery ──
section "Stale PID Recovery"
echo "99999" > ~/.sabbatical/server.pid
poetry run sabbatical server up 2>/dev/null

if wait_for_server; then
    pass "Server starts despite stale PID file"
else
    fail "Server failed to start with stale PID file"
fi

poetry run sabbatical server down 2>/dev/null
sleep 2

# ── Summary ──
echo -e "\n=========================================="
echo "Server Lifecycle: $PASS passed, $FAIL failed"
echo "=========================================="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
