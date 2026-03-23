# ============================================================
# STATUS
# ============================================================

# Get server status
curl -s http://127.0.0.1:7420/api/status | jq

# Shutdown server (graceful)
curl -s -X POST http://127.0.0.1:7420/api/shutdown | jq


# ============================================================
# ORGANIZATIONS
# ============================================================

# Create organization
curl -s -X POST http://127.0.0.1:7420/api/organizations \
  -H "Content-Type: application/json" \
  -d '{"name": "my_org", "workspace_path": "/home/whitman/workspace", "description": "My organization"}' | jq

# List all organizations
curl -s http://127.0.0.1:7420/api/organizations | jq

# Get organization by name
curl -s http://127.0.0.1:7420/api/organizations/my_org | jq

# Update organization
curl -s -X PATCH http://127.0.0.1:7420/api/organizations/my_org \
  -H "Content-Type: application/json" \
  -d '{"description": "Updated description"}' | jq

# Delete organization
curl -s -X DELETE http://127.0.0.1:7420/api/organizations/my_org


# ============================================================
# AGENTS
# ============================================================

# Create agent
curl -s -X POST http://127.0.0.1:7420/api/organizations/my_org/agents \
  -H "Content-Type: application/json" \
  -d '{"name": "my_agent", "description": "My agent", "boss": null, "instructions_path": "/home/whitman/workspace/agent.md", "max_iterations": 50}' | jq

# List agents in organization
curl -s http://127.0.0.1:7420/api/organizations/my_org/agents | jq

# List agents including removed
curl -s "http://127.0.0.1:7420/api/organizations/my_org/agents?include_removed=true" | jq

# Get agent details
curl -s http://127.0.0.1:7420/api/organizations/my_org/agents/my_agent | jq

# Update agent
curl -s -X PATCH http://127.0.0.1:7420/api/organizations/my_org/agents/my_agent \
  -H "Content-Type: application/json" \
  -d '{"description": "Updated description", "max_iterations": 100}' | jq

# Delete (soft-remove) agent
curl -s -X DELETE http://127.0.0.1:7420/api/organizations/my_org/agents/my_agent | jq


# ============================================================
# TASKS
# ============================================================

# Create task (assign to user)
curl -s -X POST http://127.0.0.1:7420/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "My task", "organization": "my_org", "assignee": "user", "description": "Task description"}' | jq

# Create task (assign to agent — auto-queued)
curl -s -X POST http://127.0.0.1:7420/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Agent task", "organization": "my_org", "assignee": "my_agent"}' | jq

# List all tasks
curl -s http://127.0.0.1:7420/api/tasks | jq

# List tasks filtered by organization
curl -s "http://127.0.0.1:7420/api/tasks?organization=my_org" | jq

# List tasks filtered by status
curl -s "http://127.0.0.1:7420/api/tasks?status=open" | jq

# List tasks filtered by assignee
curl -s "http://127.0.0.1:7420/api/tasks?assignee=my_agent" | jq

# Get task details
curl -s http://127.0.0.1:7420/api/tasks/SABT-0001 | jq

# Add comment to task
curl -s -X POST http://127.0.0.1:7420/api/tasks/SABT-0001/comments \
  -H "Content-Type: application/json" \
  -d '{"body": "This is a comment. Mention @my_agent to reassign."}' | jq

# Mark task as done
curl -s -X POST http://127.0.0.1:7420/api/tasks/SABT-0001/done | jq

# Reopen a done task
curl -s -X POST http://127.0.0.1:7420/api/tasks/SABT-0001/reopen | jq

# Preempt a running task
curl -s -X POST http://127.0.0.1:7420/api/tasks/SABT-0001/preempt | jq

# Cancel a task
curl -s -X POST http://127.0.0.1:7420/api/tasks/SABT-0001/cancel | jq


# ============================================================
# RUNS
# ============================================================

# List runs for a task
curl -s http://127.0.0.1:7420/api/tasks/SABT-0001/runs | jq

# Get run details
curl -s http://127.0.0.1:7420/api/runs/<run_id> | jq


# ============================================================
# SESSIONS
# ============================================================

# Create chat session with org scope
curl -s -X POST http://127.0.0.1:7420/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"organization_scope": "my_org"}' | jq

# Create chat session without org scope
curl -s -X POST http://127.0.0.1:7420/api/sessions \
  -H "Content-Type: application/json" \
  -d '{}' | jq

# List all sessions
curl -s http://127.0.0.1:7420/api/sessions | jq

# List sessions filtered by org
curl -s "http://127.0.0.1:7420/api/sessions?organization_scope=my_org" | jq

# Get session details
curl -s http://127.0.0.1:7420/api/sessions/<session_id> | jq

# Send message (SSE streaming)
curl -s -N -X POST http://127.0.0.1:7420/api/sessions/<session_id>/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello, what can you help me with?"}'
