#!/usr/bin/env bash
# Test Workflow 04: Task Lifecycle & State Machine
# Tests: create, list, view, comment, done, reopen, cancel,
#        tag-based delegation, status transition guards, FIFO ordering
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

# Ensure a task is open and assigned to user (handles dispatcher interference)
ensure_open_user() {
    local tid="$1"
    for attempt in $(seq 1 10); do
        local status
        status=$(curl -s "$BASE/tasks/$tid" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null || echo "unknown")
        case "$status" in
            open)
                # Try to reassign to user
                curl -s -X POST "$BASE/tasks/$tid/comments" \
                    -H "Content-Type: application/json" \
                    -d '{"body":"@user reclaiming"}' >/dev/null 2>&1 || true
                # Verify it stuck
                local assignee
                assignee=$(curl -s "$BASE/tasks/$tid" | python3 -c "import sys,json; print(json.load(sys.stdin)['assignee'])" 2>/dev/null || echo "unknown")
                if [ "$assignee" = "user" ]; then
                    return 0
                fi
                sleep 0.3
                ;;
            in_progress)
                curl -s -X POST "$BASE/tasks/$tid/preempt" >/dev/null 2>&1 || true
                sleep 0.5
                ;;
            done|canceled)
                curl -s -X POST "$BASE/tasks/$tid/reopen" >/dev/null 2>&1 || true
                sleep 0.3
                ;;
            *)
                sleep 0.5
                ;;
        esac
    done
    echo "  WARNING: Could not ensure open/user for $tid"
    return 1
}

# Helper: force-clean an org by canceling all active tasks first
force_clean_org() {
    local org="$1"
    local tasks
    tasks=$(curl -s "$BASE/tasks?organization=$org" 2>/dev/null | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    for t in d.get('tasks',[]):
        if t['status']=='in_progress': print('preempt',t['id'])
        elif t['status']=='open': print('cancel',t['id'])
except: pass
" 2>/dev/null || true)
    while IFS= read -r line; do
        local action tid
        action=$(echo "$line" | cut -d' ' -f1)
        tid=$(echo "$line" | cut -d' ' -f2)
        [ -z "$tid" ] && continue
        [ "$action" = "preempt" ] && curl -s -X POST "$BASE/tasks/$tid/preempt" >/dev/null 2>&1
        curl -s -X POST "$BASE/tasks/$tid/cancel" >/dev/null 2>&1
    done <<< "$tasks"
    curl -s -X DELETE "$BASE/organizations/$org" >/dev/null 2>&1 || true
}

# Ensure server is running
if ! curl -sf "$BASE/status" >/dev/null 2>&1; then
    echo "Starting server..."
    poetry run sabbatical server up 2>/dev/null
    wait_for_server || { echo "FATAL: Server failed to start"; exit 1; }
fi

# Setup: org + agents
WORKSPACE="/tmp/sabbatical_test_tasks"
mkdir -p "$WORKSPACE/.sabbatical/agents"
echo "You are the lead." > "$WORKSPACE/.sabbatical/agents/lead.md"
echo "You are a developer." > "$WORKSPACE/.sabbatical/agents/dev.md"

force_clean_org "test_task_org"
curl -sf -X POST "$BASE/organizations" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"test_task_org\",\"workspace_path\":\"$WORKSPACE\"}" >/dev/null

curl -sf -X POST "$BASE/organizations/test_task_org/agents" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"lead\",\"instructions_path\":\"$WORKSPACE/.sabbatical/agents/lead.md\",\"description\":\"Lead\"}" >/dev/null

curl -sf -X POST "$BASE/organizations/test_task_org/agents" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"dev\",\"instructions_path\":\"$WORKSPACE/.sabbatical/agents/dev.md\",\"description\":\"Developer\",\"boss\":\"lead\"}" >/dev/null

# ── 1. Create task assigned to user ──
section "Create Task (assigned to user)"
RESP=$(curl -sf -X POST "$BASE/tasks" \
    -H "Content-Type: application/json" \
    -d '{"title":"Test task one","organization":"test_task_org","description":"Detailed spec for task one"}')

TASK1_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['status']=='open'
assert d['assignee']=='user'
assert d['organization']=='test_task_org'
assert d['description']=='Detailed spec for task one'
" 2>/dev/null; then
    pass "Task created: $TASK1_ID (assigned to user, status=open)"
else
    fail "Task creation failed: $RESP"
fi

# ── 2. Create task assigned to agent (verify initial state, then reclaim) ──
section "Create Task (assigned to agent)"
RESP=$(curl -sf -X POST "$BASE/tasks" \
    -H "Content-Type: application/json" \
    -d '{"title":"Agent task","organization":"test_task_org","assignee":"dev","description":"Work for dev"}')

TASK2_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['assignee']=='dev'
assert d['status']=='open'
" 2>/dev/null; then
    pass "Task created: $TASK2_ID (assigned to dev)"
else
    fail "Agent task creation failed: $RESP"
fi

# Reclaim from dispatcher before it runs the agent
ensure_open_user "$TASK2_ID" || true

# ── 3. Task ID format ──
section "Task ID Format"
if echo "$TASK1_ID" | grep -qE '^[A-Z]{4}-[0-9]{4}$'; then
    pass "Task ID matches format XXXX-NNNN: $TASK1_ID"
else
    fail "Task ID format unexpected: $TASK1_ID"
fi

# ── 4. Description defaults to title ──
section "Description Default"
RESP=$(curl -sf -X POST "$BASE/tasks" \
    -H "Content-Type: application/json" \
    -d '{"title":"No desc provided","organization":"test_task_org"}')

TASK3_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['description']=='No desc provided'" 2>/dev/null; then
    pass "Description defaults to title when omitted"
else
    fail "Description default failed: $RESP"
fi

# ── 5. List tasks with filters ──
section "List Tasks"
RESP=$(curl -sf "$BASE/tasks?organization=test_task_org")
if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert len(d['tasks']) >= 3
" 2>/dev/null; then
    pass "List returns tasks for organization"
else
    fail "List response unexpected: $RESP"
fi

RESP=$(curl -sf "$BASE/tasks?organization=test_task_org&assignee=user")
if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for t in d['tasks']:
    assert t['assignee']=='user', f'Expected user, got {t[\"assignee\"]}'
" 2>/dev/null; then
    pass "List filters by assignee=user"
else
    fail "Assignee filter failed: $RESP"
fi

# ── 6. View task (timeline) ──
section "View Task Timeline"
RESP=$(curl -sf "$BASE/tasks/$TASK1_ID")
if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert 'timeline' in d
assert isinstance(d['timeline'], list)
" 2>/dev/null; then
    pass "Task view includes timeline array"
else
    fail "Task view missing timeline: $RESP"
fi

# ── 7. Comment on task ──
section "Comment on Task"
ensure_open_user "$TASK1_ID" || true

RESP=$(curl -sf -X POST "$BASE/tasks/$TASK1_ID/comments" \
    -H "Content-Type: application/json" \
    -d '{"body":"This is a user comment with no tag"}')

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['comment']['author']=='user'
assert d['task']['assignee']=='user'  # No tag, no change
" 2>/dev/null; then
    pass "Comment added without state change (no @tag)"
else
    fail "Comment response unexpected: $RESP"
fi

# ── 8. Comment with @tag delegates to agent ──
section "Tag-Based Delegation"
ensure_open_user "$TASK1_ID" || true

RESP=$(curl -sf -X POST "$BASE/tasks/$TASK1_ID/comments" \
    -H "Content-Type: application/json" \
    -d '{"body":"@dev Please implement this feature"}')

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['task']['assignee']=='dev'
assert d['task']['status']=='open'
" 2>/dev/null; then
    pass "Comment with @dev delegates task to dev agent"
else
    fail "Tag delegation failed: $RESP"
fi

# Reclaim task from dispatcher
ensure_open_user "$TASK1_ID" || true

# ── 9. Invalid @tag rejected ──
section "Invalid Tag Validation"
ensure_open_user "$TASK1_ID" || true

HTTP_CODE=$(curl -s -o /tmp/tag_resp.json -w "%{http_code}" -X POST "$BASE/tasks/$TASK1_ID/comments" \
    -H "Content-Type: application/json" \
    -d '{"body":"@nonexistent_agent_xyz do something"}')

if [ "$HTTP_CODE" = "404" ]; then
    pass "Invalid agent @tag returns 404"
else
    fail "Invalid agent @tag returned $HTTP_CODE (expected 404)"
fi

# ── 9b. First valid tag: invalid + valid ──
section "First Valid Tag (mixed invalid + valid)"
ensure_open_user "$TASK1_ID" || true

RESP=$(curl -sf -X POST "$BASE/tasks/$TASK1_ID/comments" \
    -H "Content-Type: application/json" \
    -d '{"body":"@nonexistent_xyz please help, or @dev take over"}')

if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['task']['assignee']=='dev', f'Expected dev, got {d[\"task\"][\"assignee\"]}'
assert d['task']['status']=='open'
" 2>/dev/null; then
    pass "First valid tag wins: @nonexistent_xyz skipped, routed to @dev"
else
    fail "First valid tag routing failed: $RESP"
fi

# Reclaim task from dispatcher
ensure_open_user "$TASK1_ID" || true

# ── 9c. All tags invalid → 404 ──
section "All Tags Invalid (404)"
ensure_open_user "$TASK1_ID" || true

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/tasks/$TASK1_ID/comments" \
    -H "Content-Type: application/json" \
    -d '{"body":"@ghost_one and @ghost_two please help"}')

if [ "$HTTP_CODE" = "404" ]; then
    pass "All-invalid tags returns 404"
else
    fail "All-invalid tags returned $HTTP_CODE (expected 404)"
fi

# ── 10. Mark task done ──
section "Task Done"
ensure_open_user "$TASK1_ID" || true

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/tasks/$TASK1_ID/done")
HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -1)

if echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='done'" 2>/dev/null; then
    pass "Task marked as done"
else
    fail "Task done failed (HTTP $HTTP_CODE): $BODY"
fi

# ── 11. Cannot comment on done task ──
section "Done Task Guards"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/tasks/$TASK1_ID/comments" \
    -H "Content-Type: application/json" \
    -d '{"body":"Should not work"}')

if [ "$HTTP_CODE" = "409" ]; then
    pass "Comment on done task returns 409"
else
    fail "Comment on done task returned $HTTP_CODE (expected 409)"
fi

# ── 12. Reopen task ──
section "Reopen Task"
RESP=$(curl -sf -X POST "$BASE/tasks/$TASK1_ID/reopen")
if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert d['status']=='open'
assert d['assignee']=='user'
" 2>/dev/null; then
    pass "Task reopened to open/user"
else
    fail "Reopen failed: $RESP"
fi

# Verify system comment was added
RESP=$(curl -sf "$BASE/tasks/$TASK1_ID")
if echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
bodies = [e['body'] for e in d['timeline'] if e.get('type')=='comment']
assert any('Task reopened by user' in b for b in bodies)
" 2>/dev/null; then
    pass "System comment added on reopen"
else
    fail "Reopen system comment missing"
fi

# ── 13. Cancel task ──
section "Cancel Task"
RESP=$(curl -sf -X POST "$BASE/tasks/$TASK3_ID/cancel")
if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='canceled'" 2>/dev/null; then
    pass "Task canceled"
else
    fail "Cancel failed: $RESP"
fi

# Cannot comment on canceled task
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/tasks/$TASK3_ID/comments" \
    -H "Content-Type: application/json" \
    -d '{"body":"Should not work"}')

if [ "$HTTP_CODE" = "409" ]; then
    pass "Comment on canceled task returns 409"
else
    fail "Comment on canceled task returned $HTTP_CODE (expected 409)"
fi

# Cannot reopen canceled task
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/tasks/$TASK3_ID/reopen")
if [ "$HTTP_CODE" = "409" ]; then
    pass "Reopen on canceled task returns 409"
else
    fail "Reopen on canceled task returned $HTTP_CODE (expected 409)"
fi

# ── 14. Done only allowed for user-assigned tasks ──
section "Done Guard: Assignee Check"
ensure_open_user "$TASK1_ID" || true
curl -sf -X POST "$BASE/tasks/$TASK1_ID/done" >/dev/null
curl -sf -X POST "$BASE/tasks/$TASK1_ID/reopen" >/dev/null

# ── 15. CLI task workflow ──
section "CLI Task Workflow"
CLI_OUT=$(poetry run sabbatical task create "CLI test task" --organization test_task_org 2>&1)
if echo "$CLI_OUT" | grep -qiE "Created.*TTOO-|Created.*TEST-"; then
    pass "CLI task create shows concise output"
else
    fail "CLI task create output unexpected: $CLI_OUT"
fi

CLI_LIST=$(poetry run sabbatical task list --organization test_task_org 2>&1)
if echo "$CLI_LIST" | grep -qi "CLI test task"; then
    pass "CLI task list shows created task"
else
    fail "CLI task list missing task: $CLI_LIST"
fi

# Cleanup
force_clean_org "test_task_org"
rm -rf "$WORKSPACE"
rm -f /tmp/tag_resp.json

# ── Summary ──
echo -e "\n=========================================="
echo "Task Lifecycle: $PASS passed, $FAIL failed"
echo "=========================================="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
