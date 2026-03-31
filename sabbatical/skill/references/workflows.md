# Common Workflows

## Plan and Break Down Work

Before creating anything in Sabbatical, help the user plan. This is the most important workflow.

```
1. User says: "I need to add Stripe webhook handling to the payments service"

2. You ask clarifying questions:
   - What events do you need to handle?
   - Is there an existing webhook infrastructure or is this from scratch?
   - Does the team already exist in Sabbatical?

3. You propose a plan:
   "Here's how I'd break this down for the payments team:

   Task 1: 'Implement Stripe webhook endpoint with signature verification'
   — The team will build the /webhooks/stripe POST handler, verify signatures,
     and parse event types.

   Task 2: 'Add event handlers for payment_intent.succeeded and payment_intent.failed'
   — The team will implement the business logic for the two critical event types,
     update order status, and trigger notifications.

   Task 3: 'Add webhook replay protection and idempotent event processing'
   — The team will ensure duplicate webhook deliveries don't cause duplicate
     side effects.

   Want me to create these three tasks?"

4. User confirms → you create the tasks via MCP tools.
```

**Key principles for breaking down work:**
- Each task should be a meaningful goal that multiple agents can contribute to — not a single-file change.
- Tasks should be independent enough that the team can work on them in sequence without the first one being a blocker for the second (when possible).
- Write the task description with enough context that the root agent can scope it without asking the user. Include the *why*, not just the *what*.
- If you're unsure about the right granularity, ask the user.

## Set Up a New Project

When the user wants to create a new team, help them design the structure, write the instruction files, and create the resources — in that order.

```
1. get_status()
   → confirm dispatcher is running

2. Discuss team structure with the user:
   "What kind of project is this? What specialties do you need?
    A typical team has a lead (root) who scopes and reviews,
    specialists who implement, and optionally a test writer."

3. Propose and confirm:
   "Here's what I'd suggest for the payments service:

    lead_dev (root) — scopes tasks, delegates, reviews before returning to you
    ├── backend_dev — Python APIs, database logic, integrations
    └── test_writer — unit tests, integration tests

    I'll write the instruction files for each agent and place them
    in .sabbatical/agents/ inside the workspace.
    Does this look right?"

4. After user confirms, write the .md instruction files:
   - Each file defines the agent's role, behavior, team awareness, and escalation rules
   - Save them to a predictable location (e.g., <workspace>/.sabbatical/agents/)
   - Use absolute paths when creating agents

5. Create the resources:
   create_organization(name="payments", workspace_path="/absolute/path/to/project")
   create_agent(organization="payments", name="lead_dev",
               instructions_path="/absolute/path/to/project/.sabbatical/agents/lead_dev.md")
   create_agent(organization="payments", name="backend_dev",
               instructions_path="/absolute/path/to/project/.sabbatical/agents/backend_dev.md",
               boss="lead_dev")
   create_agent(organization="payments", name="test_writer",
               instructions_path="/absolute/path/to/project/.sabbatical/agents/test_writer.md",
               boss="lead_dev")
```

**Team design rules:**
- Always start with at least one root agent (no boss). This is the team's entry point and decision-maker.
- Root agents' instructions files must list all team members and their specialties.
- Each specialist's instructions should explain their expertise and who else is on the team.
- Don't create agents for one-off tasks — agents are permanent team members.
- You are responsible for writing the instruction files. Don't ask the user to write them — propose the content, confirm, and create them.

## Monitor Progress

```
get_status()
  → overall health, active workers, total cost

list_tasks(organization="payments", status="in_progress")
  → what's running right now

get_task("PAYM-0001")
  → full timeline: all comments and run summaries

list_runs("PAYM-0001")
  → execution history per run

get_run("<run_id>")
  → step-by-step: reasoning, tool calls, output
```

## Steer or Intervene on a Task

These operations are for **correcting course on an existing task** — not for initial assignment. New tasks should always go through the root agent first.

```
# Redirect to a specific agent (intervention, not initial routing)
add_comment(task_id="PAYM-0001", body="This needs research first @researcher")

# Take over a running task
preempt_task(task_id="PAYM-0001")
  → task becomes open, assigned to user

# Give feedback and send back to the team
add_comment(task_id="PAYM-0001", body="Good start, also handle edge cases @lead_dev")

# Retry a failed task
retry_task(task_id="PAYM-0001", assignee="lead_dev")
```

**When to intervene:**
- The agent got stuck or went off track — preempt and redirect.
- You have new context the team needs — add a comment with the info and tag the relevant agent.
- A task failed due to a transient error — retry it.

**When not to intervene:**
- The task was just created — let the root agent triage it.
- An agent is still working — wait for it to finish unless it's clearly going wrong.

## Complete or Clean Up

```
# A task was assigned to user after the team finished — review and close it
get_task("PAYM-0001")                 # read the timeline first
complete_task(task_id="PAYM-0001")   # mark done (confirm with user first)

# Cancel work that's no longer needed (confirm with user — this is irreversible)
cancel_task(task_id="PAYM-0002")

# Reopen a completed task for more work
reopen_task(task_id="PAYM-0001")     # status → open, assignee → user
add_comment(task_id="PAYM-0001", body="Also add pagination @lead_dev")
```

## Write Effective Tasks

The most common mistake is writing tasks that are too narrow — step-level instructions for a single agent. Sabbatical tasks are team work. Every task should describe a goal that multiple agents contribute to.

**Good tasks describe outcomes:**
```
Title: "Add idempotency keys to the charge endpoint"
Description: "Duplicate POST requests to /charges are creating duplicate charges
in production. Add an idempotency key mechanism: clients pass an Idempotency-Key
header, the server stores it and returns the cached response for repeated requests.
Keys should expire after 24 hours."
```

The root agent can scope this, the backend dev can implement it, the test writer can validate it, the root agent can review it. Every agent has a reason to contribute.

**Bad tasks describe steps:**
```
Title: "Add idempotency_keys table migration"
Title: "Change line 94 in handler.py"
Title: "Write tests for the idempotency check"
```

These are micro-tasks that bypass the team's collaboration model. The root agent can't meaningfully triage them — they're pre-triaged instructions for specific agents.

**Rule of thumb:** if you can picture only one agent working on a task, it's too narrow. Widen the scope to the goal, not the step.

## Write Effective Agent Instructions

When creating agents, **you write the instruction files**. Don't ask the user to create them — propose the content, get confirmation, and write the `.md` files yourself to a predictable location inside the workspace (e.g., `<workspace>/.sabbatical/agents/`).

Agent instructions are a plain markdown file. The quality of the instructions determines the quality of the team. Every instruction file should include:

- **Role and expertise** — what the agent is responsible for, what it's good at.
- **Behavior on receiving a task** — should it triage and delegate? Implement directly? Review?
- **Team awareness** — list every other agent by `@name` with a one-liner on their specialty, so the agent knows who to hand off to.
- **Escalation rules** — when to tag `@user` (blockers, ambiguity, approval needed).

Example (`lead_dev.md`):
```markdown
# lead_dev

You are the lead developer for the payments service. You own code quality
and architecture decisions.

When you receive a task:
1. Read the full comment thread to understand context and any prior work.
2. Assess the scope — is this something you should handle directly, or
   does it need a specialist?
3. If delegating, write a clear briefing: what you've assessed, what you
   need from them, and any constraints. The next agent's only context
   is this thread.
4. When work comes back to you for review, evaluate quality and either
   approve (tag @user) or request changes (tag the specialist).

Your team:
- @backend_dev — Python APIs, database logic, Stripe integration
- @test_writer — unit tests, integration tests, coverage

Escalate to @user when you need clarification on requirements,
when a task is ambiguous, or when you need a product decision.
```

## Tips

- **Always call `get_status()` first** to confirm the dispatcher is running.
- **Read the full timeline** with `get_task()` before intervening — understand context before acting.
- **Ask the user before creating resources.** Never create organizations, agents, or tasks without explicit confirmation.
- **Let the root agent triage.** Don't manually route freshly created tasks — that bypasses the team's decision-making.
- **Tasks assigned to `user` are paused.** The dispatcher only picks up tasks assigned to agents.
- **Cost is tracked per-run** and aggregated at task, agent, and organization levels.
- **`preempt_task` is the only way to stop a running task** — it cannot be canceled mid-run directly.
- **`cancel_task` is irreversible.** Prefer `preempt_task` + `complete_task` if you just want to stop work gracefully. Confirm with the user before canceling.
