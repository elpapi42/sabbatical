# Sabbatical Concepts

## Organizations

An isolated workspace where agents collaborate on tasks. Maps to a real team boundary — a backend platform team, a payments squad, a mobile client team — scoped to a directory on disk.

- **Name**: Unique `snake_case` identifier (e.g., `payments`, `backend_platform`). Reserved: `user`, `system`.
- **Workspace path**: Absolute filesystem path. All agent file operations are sandboxed here.
- **Description**: Optional purpose statement injected into agent prompts.

Organizations are fully isolated — agents in one cannot interact with another. Deleting an organization cascades to all its agents, tasks, and runs (irreversible; blocked if any tasks are `in_progress`).

## Agents

A stateless AI worker defined entirely by a markdown instructions file. The file is the agent's identity — its expertise, style, and role. It is read fresh on every run.

**Properties:**
- **Name**: Unique within the org (`snake_case`).
- **Instructions path**: Absolute path to a `.md` file.
- **Boss**: Optional parent agent. Omit to create a root agent.
- **Max iterations**: LLM turn limit per run (default: 50). Circuit breaker for runaway execution.
- **Model**: Optional LLM override (e.g., `google/gemini-2.5-flash`).

**Hierarchy:** Agents form a tree (or forest) via `boss` relationships. The hierarchy is critical to how Sabbatical works:

- **Root agents** (no boss) are the entry points for tasks. When a task is created, it auto-assigns to one of the organization's root agents. Root agents are the team's decision-makers — they scope work, triage, delegate to specialists, and review results before returning them to the user. An organization can have multiple root agents; tasks are distributed among them automatically.
- **Specialists** report to a root agent (or to another specialist). They have distinct, non-overlapping expertise. Their instructions should explain their specialty and list the other agents they collaborate with.
- Without root agents that triage, tasks don't get the scoping step that makes multi-agent collaboration work. A flat set of peer agents with no hierarchy will produce uncoordinated, redundant work.

An organization must have at least one root agent before tasks can be created.

Removing an agent is a **soft-delete**: it's preserved for history and its subordinates are promoted to root.

## Tasks

A task is a **goal for the team**, not a work item for a single agent.

When you create a task, it auto-assigns to a root agent and enters the dispatch queue. The root agent reads the spec, decides how to approach it, and either handles it directly or delegates to a specialist via `@mention`. That specialist does their part and hands off to the next agent. The task flows through the team — each agent contributes from their unique expertise — until someone tags `@user` to say the work is ready for review.

This means every task should be written so that **multiple agents have a reason to contribute**. The root agent scopes it, the specialist implements it, the test writer validates it, the root agent reviews it. If a task only makes sense for one agent, it's too narrow.

### Good vs Bad Tasks

**Good — describes an outcome the team can work toward:**
- "Add idempotency keys to the charge endpoint so duplicate POST requests don't create duplicate charges"
- "Migrate the webhook handler from synchronous to async processing"
- "Add comprehensive error handling to the payment flow — surface clear error messages to the client and log structured errors for debugging"

**Bad — step-level instructions for one agent:**
- "Change line 94 in handler.py to add the idempotency check"
- "backend_dev: write the migration file for the idempotency_keys table"
- "Run the test suite and fix any failures"

**Bad — tasks manually routed to a specific agent after creation:**
- Creating a task and immediately adding a comment with `@backend_dev` to bypass the root agent's triage step

### Task IDs

Auto-generated from the org name:
- Single-word org: first 4 chars uppercased → `SABB-0001`
- Multi-word org: initials (padded to 4) → `my_cool_project` → `MCP-0001`

IDs increment per org: `XXXX-0001`, `XXXX-0002`, …

### Statuses

```
create_task ──► open (assigned to root agent, queued)
                 │
        dispatcher picks up
                 │
                 ▼
            in_progress (agent running)
               / | \
              ▼  ▼  ▼
           done failed preempted → open (assigned to user)
            │     │
            │     ├── retry_task → open (re-queued)
            │     └── reopen_task → open (assigned to user)
            │
            ├── reopen_task → open (assigned to user)
            └── retry_task → open (re-queued)

cancel_task ──► canceled (irreversible, from any non-terminal state)
```

## Runs

One execution attempt of a task by an agent. A task typically has **multiple runs** — one per agent handoff — not just retries. For example: `lead_dev` runs first (scoping), hands off to `backend_dev` (implementation), who hands off to `test_writer` (testing), who hands off back to `lead_dev` (review). That's four runs on a single task, and that's normal.

**Run statuses:** `running`, `success`, `failed`, `preempted`

**Execution steps** recorded per run:
- `llm_reasoning` — agent's internal reasoning text
- `tool_call` — tool invocation with name, arguments, and output
- `fatal_error` — error message when the run crashed

## Comments

Append-only messages on the task thread. The primary mechanism for collaboration between agents and communication with the user.

The comment thread is the team's shared memory. Every agent reads the full thread before starting work, so context accumulates naturally across handoffs. Each agent sees what every previous agent wrote — but not their internal tool calls or reasoning.

**Routing via @mentions:**
- When an agent finishes, the last valid `@tag` in its last comment determines routing
- `@agent_name` reassigns the task to that agent and re-queues it
- `@user` assigns the task back to the human
- No valid `@tag` → thread fallback scans for mentioned agents who haven't run since their mention, then escalates to boss, then `@user`

Comments can only be added when a task is `open` or `failed` (not `in_progress`, `done`, or `canceled`).

Only valid, active (non-removed) agent names are accepted as routing targets.

## Timeline

The merged chronological view of a task's comments and run summaries. Retrieved via `get_task`. Each entry is either:

```json
{"type": "comment", "author": "user|system|agent_name", "body": "...", "created_at": "..."}
```
```json
{"type": "run_summary", "run_id": "...", "agent": "...", "status": "running|success|failed|preempted",
 "duration_seconds": 12.5, "cost": 0.03, "started_at": "...", "ended_at": "..."}
```

## Dispatcher

The dispatcher is a background daemon that polls for `open` tasks assigned to agents and runs them concurrently up to the configured `max_concurrency` limit. It starts automatically when the MCP server connects. Tasks assigned to `user` are ignored by the dispatcher.
