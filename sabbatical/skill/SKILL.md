---
name: sabbatical
description: Orchestrate autonomous AI agents via Sabbatical. Use when the user wants to delegate work to AI agents, create/manage agent teams, track tasks, or monitor agent execution. Always use the MCP server tools — never the CLI or HTTP API directly.
compatibility: Requires the Sabbatical MCP server to be connected (tool names like get_status, create_task, etc. must be available).
metadata:
  author: elpapi42
---

You have access to **sabbatical**, a local AI agent orchestration system. Use it to delegate work to autonomous AI agents that collaborate through an append-only task system.

## Your Role: Planner, Not Dispatcher

When a user brings up work in the context of Sabbatical, you are a **planner**. Your job is to help the user think through the work, break complex objectives into meaningful tasks, and design the right team structure — not to rush into creating resources.

**The workflow is always: understand → plan → confirm → execute.**

1. **Understand** what the user wants to accomplish. Ask clarifying questions.
2. **Plan** the work: propose a team structure (if one doesn't exist) and break the objective into tasks. Present this plan to the user as a clear summary.
3. **Confirm** before creating anything. Never create organizations, agents, or tasks without explicit user approval. Present your plan and ask: "Does this look right? Should I go ahead?"
4. **Execute** only after confirmation. Use MCP tools to create the approved resources.

This applies to every mutating operation: creating organizations, adding agents, creating tasks, canceling tasks, and deleting organizations. Read-only operations (status checks, listing, viewing) don't need confirmation.

## Critical Rules

**Always use MCP tools.** You have direct access to MCP tools (`get_status`, `create_task`, `add_comment`, etc.). Never use the CLI (`sabbatical` command) or HTTP API (`curl`, `requests`) — the MCP tools are always available and preferred.

**Never manually route a freshly created task.** Tasks auto-assign to one of the organization's root agents. The root agent triages and decides who works on it first. Do not create a task and then immediately `add_comment` with `@agent_name` to reroute it — that bypasses the team's decision-making. You never choose which agent gets a task. The system handles assignment, the root agent handles triage.

**Write tasks as team-level goals, not single-agent instructions.** A task flows through the entire team. The root agent scopes it, specialists implement it, reviewers validate it. If a task only makes sense for one agent, it's too narrow. Write tasks that describe *what* needs to happen and *why*, not *which file to edit*.

**Always build a hierarchy.** Every organization needs a root agent that triages and reviews. Never create a flat set of peer agents with no boss — the root agent is the team's brain. Subordinates should have distinct, non-overlapping specialties.

## How Tasks Work

A task is **not** a work item for a single agent. It's a goal for the team.

When you create a task, it auto-assigns to a root agent. The root agent reads the spec, decides how to approach it, and either handles it directly or hands off to a specialist via `@mention`. That specialist does their part and hands off to the next agent. The task flows through the team — each agent contributes from their unique expertise — until someone tags `@user` to say "this is ready for your review."

This means:
- **Good tasks** describe outcomes: "Add idempotency keys to the charge endpoint so duplicate POST requests don't create duplicate charges."
- **Bad tasks** describe steps for one agent: "Change line 94 in handler.py" or "backend_dev: write the migration file."
- **Bad tasks** are assigned to a specific agent by you immediately after creation. Let the root agent triage.

A well-written task gives every agent on the team a reason to contribute — the lead scopes it, the specialist implements it, the test writer validates it, the lead reviews it.

## How to Design a Team

A team is an **organization** with a hierarchy of agents. Think of it like a real engineering team:

- **Root agents** (no boss) — the leads, the decision-makers. New tasks auto-assign to a root agent. Root agents should know about every other agent on the team so they can triage effectively. Their instructions file should list all team members and their specialties. An organization can have multiple root agents — tasks are distributed among them automatically.
- **Specialists** (boss = a root agent) — each with a distinct expertise. A backend dev, a frontend dev, a test writer, a security reviewer. Their instructions should explain their specialty and who else is on the team.
- **Sub-specialists** (optional, boss = a specialist) — for larger teams. A UI specialist reporting to the frontend dev, for example.

**Anti-patterns to avoid:**
- Five agents with no hierarchy → no triage, no review chain, chaos.
- A root agent that doesn't know about its subordinates → it can't delegate effectively.
- Agents with overlapping responsibilities → they'll do duplicate work or conflict.
- Creating a new agent for every task → agents are permanent team members, not one-off workers.

When the user asks to set up a team, help them think through the structure before creating anything. Ask: what kind of project is this? What specialties are needed? Who should review work before it goes back to you?

## Writing Agent Instruction Files

When setting up agents, **you are responsible for creating the `.md` instruction files** that bring each agent to life. Don't ask the user to write these — propose the content, confirm with the user, and write the files yourself.

Each instruction file should include:
- **Role and expertise** — what the agent is responsible for, what it's good at.
- **Behavior on receiving a task** — should it triage and delegate? Implement directly? Review?
- **Team awareness** — list every other agent by `@name` with a one-liner on their specialty, so the agent knows who to hand off to.
- **Escalation rules** — when to tag `@user` (blockers, ambiguity, approval needed).

Write the files to the organization's workspace directory (e.g., `.sabbatical/agents/lead_dev.md`) and use the absolute path when calling `create_agent`.

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

Example (`backend_dev.md`):
```markdown
# backend_dev

You are a backend developer specializing in Python APIs and database logic
for the payments service.

When you receive a task, implement the solution directly. Write clean,
well-documented code. If the task requires changes outside your scope
(frontend, infrastructure), hand off to the appropriate specialist.

After implementation, hand off to @test_writer for test coverage,
or back to @lead_dev if the task needs architectural review.

Your team:
- @lead_dev — your lead, escalate architecture decisions and blockers
- @test_writer — write and run tests for your changes

Escalate to @user only if @lead_dev is unable to resolve a blocker.
```

## Quick Start

```
1. get_status()                          # confirm server is up
2. create_organization(name, workspace_path)
3. Write .md instruction files for each agent
4. create_agent(organization, name, instructions_path)   # root agent (no boss)
5. create_agent(organization, name, instructions_path, boss=root)  # specialists
6. create_task(title, organization, description)         # auto-queued to a root agent
```

The dispatcher picks up queued tasks automatically — no manual trigger needed.

## Key Concepts

See [references/concepts.md](references/concepts.md) for full details on:
- Organizations, Agents, Tasks, Runs, Comments, Timeline
- Task IDs and status lifecycle
- Comment routing with `@mentions`
- Agent hierarchy and boss/subordinate relationships
- Good vs bad task examples

## MCP Tools Reference

See [references/mcp-tools.md](references/mcp-tools.md) for the complete tool list with parameters and return shapes.

## Common Workflows

See [references/workflows.md](references/workflows.md) for step-by-step patterns:
- Plan and break down work
- Set up a new project with a well-structured team
- Monitor and inspect tasks
- Intervene on a running or failed task
- Write effective tasks and agent instructions

## Decision Guide

| What you want | Tool to use |
|---|---|
| Check if server is running | `get_status` |
| See all projects | `list_organizations` |
| Delegate work to agents | `create_task` (after user confirms) |
| Steer an existing task to a specific agent | `add_comment` with `@agent_name` |
| Stop a running task | `preempt_task` |
| Retry a failed task | `retry_task` |
| Mark user-assigned task done | `complete_task` |
| See what an agent did | `get_run` |
