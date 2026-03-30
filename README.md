# Sabbatical

**Stop pair programming with AI. Start managing it.**

---

You open Claude Code. You type a request. You wait. It responds. You react. You wait again. For every task, you're stuck in a synchronous loop — blocked while it works, blocking it while you think.

The workaround? More sessions. You open three Claude Code tabs, four Cursor windows, juggling contexts. Now you're a human load balancer — remembering which session is doing what, re-explaining context when one drifts, copy-pasting results between them. You traded one bottleneck for a coordination problem.

Sabbatical is a different model. You build a team of AI agents once — a lead developer, a backend specialist, a test writer, whatever your project needs. Then you dispatch tasks to them the same way a tech lead assigns tickets. The agents pick up work, collaborate through `@mentions`, hand off between specialists, and surface results when they're done, blocked, or ready for review.

Meanwhile, you're doing what you're actually good at — planning the next initiative, reviewing a PR from another team, writing a design doc, scoping the next quarter. You're not context-switching between AI sessions. You're managing a team through tasks.

It's the difference between juggling five chat windows and having a team that works from a backlog. One scales with you. The other scales against you.

```
You:          "Add idempotency keys to the charge endpoint. Assign to payments."

lead_dev:      Scoped the work. Needs DB migration + handler logic. @backend_dev
backend_dev:   Added idempotency_keys table, wrapped /charges POST in key check. @test_writer
test_writer:   Tests passing for duplicate charge rejection and key expiry. @lead_dev
lead_dev:      Reviewed. Looks good. @user

You:          "How's the idempotency task?"
Claude Code:  ✅ Done. 4 agent handoffs, 5 files changed, all tests passing.
```

Three agents. Zero interruptions. You were scoping the billing migration the whole time.

---

## 30-Second Setup

```bash
pipx install sabbatical
export OPENROUTER_API_KEY="sk-or-your-key"
sabbatical server up
```

Connect your AI tool:

```bash
# Claude Code
claude mcp add sabbatical -- sabbatical mcp
```

```json
// Cursor, Windsurf, or any MCP client
{
  "mcpServers": {
    "sabbatical": {
      "command": "sabbatical",
      "args": ["mcp"]
    }
  }
}
```

That's it. Your AI tool now has 22 MCP operations to build teams, dispatch tasks, and monitor agents.

---

## Build a Team in 60 Seconds

Organizations map to real team boundaries — a backend platform team, a payments squad, a mobile client team — each scoped to a codebase directory.

```bash
# Create an organization tied to your project
sabbatical organization create payments \
  --workspace-path ./payments-service \
  --description "Payments service team — API, billing logic, Stripe integration"

# Add agents with instruction files
sabbatical agent add lead_dev \
  --organization payments \
  --instructions ./agents/lead_dev.md

sabbatical agent add backend_dev \
  --organization payments \
  --instructions ./agents/backend_dev.md \
  --boss lead_dev

sabbatical agent add test_writer \
  --organization payments \
  --instructions ./agents/test_writer.md \
  --boss lead_dev
```

Or just tell Claude Code: *"Set up a Sabbatical org for the payments service with a lead, a backend specialist, and a test writer."* It does it through MCP.

You build the team once. Then you feed it work — daily, across sprints, across initiatives.

---

## Manage a Backlog, Not a Chat Session

This is where the model pays off. You're not dispatching one task and watching it. You're stacking work across teams like a tech lead.

```bash
# Monday morning — queue up the week
sabbatical task create "Add idempotency keys to charge endpoint" \
  --organization payments \
  --description "Wrap the /charges POST handler in idempotency logic..."

sabbatical task create "Migrate webhook handler to async" \
  --organization payments \
  --description "The Stripe webhook handler is synchronous and blocking..."

sabbatical task create "Add retry budget metrics to dashboard" \
  --organization platform \
  --description "Expose retry budget counters from the circuit breaker..."
```

Three tasks, two teams. The agents pick them up, collaborate, hand off, and surface results — while you're in a design review for something else entirely. When you come back:

```bash
sabbatical task list --organization payments --status done
sabbatical task list --organization platform --status open
```

This is the real value. Not "AI does your work while you nap." It's: **you can operate across multiple initiatives concurrently without the cognitive overhead of managing a dozen AI sessions.** The team structure absorbs that complexity. You manage tasks, not conversations.

---

## How Agents Collaborate

There's no workflow engine. No DAG. No planner. Agents collaborate through a single, dead-simple protocol:

**Every agent reads the full comment thread. Every agent ends with a `@mention`.**

- `@agent_name` → task routes to that agent
- `@user` → task comes back to you
- No valid tag → escalates to the agent's boss

That's it. The comment thread is the shared memory. Each agent sees everything every previous agent wrote — but not their internal tool calls or reasoning. Context accumulates naturally, like a well-run async standup.

The hierarchy is a safety net: if routing fails, the task escalates up the chain. If there's no boss, it lands on you. Nothing gets lost.

---

## What Makes an Agent

An agent is a `.md` file. That's the whole identity — expertise, working style, who it collaborates with.

```markdown
# lead_dev

You are the lead developer. You own code quality and architecture decisions.

When a task arrives, understand the full scope first. Execute it yourself
or delegate to the right specialist.

Your team:
- @backend_dev — Python, APIs, database logic, integrations
- @test_writer — unit tests, integration tests, coverage

When delegating, write a clear briefing: what you've already done, what
you need, and any constraints. The next agent's only context is this thread.
```

This file is injected into every run. The better your instructions, the better your team performs. Generic instructions produce generic agents.

---

## How It Works Under the Hood

At the center is a **core library** — organizations, agents, tasks, the dispatcher, the execution engine. Everything that makes Sabbatical work lives here. No network layer, no transport assumptions. Just the domain logic, a SQLite database, and agents running against your actual codebase.

On top of that core, three interfaces serve different users:

```
         ┌──────────┐   ┌─────────────┐   ┌──────────────────┐
         │   CLI    │   │ HTTP Server │   │   MCP Server     │
         │          │   │             │   │                  │
         │ terminal │   │ build tools │   │ connect AI tools │
         │ users    │   │ on top      │   │ (Claude Code,    │
         │          │   │             │   │  Cursor, etc.)   │
         └────┬─────┘   └──────┬──────┘   └────────┬─────────┘
              │                │                    │
              ▼                ▼                    ▼
         ┌───────────────────────────────────────────────┐
         │              Sabbatical Core                  │
         │                                               │
         │  Organizations · Agents · Tasks · Comments    │
         │  Dispatcher · Worker Threads · Execution      │
         │                                               │
         │  ┌───────────────────────────────────────┐    │
         │  │           SQLite Database              │    │
         │  └───────────────────────────────────────┘    │
         └───────────────────────────────────────────────┘
```

**The CLI** is for terminal-native developers who want direct control — create orgs, add agents, dispatch tasks, inspect runs.

**The HTTP server** is for anyone building other tools on top of Sabbatical — dashboards, integrations, custom workflows.

**The MCP server** is for AI tools. It exposes the full Sabbatical API as 22 MCP operations over stdio, so Claude Code, Cursor, Windsurf, or any MCP-compatible agent can orchestrate your teams natively.

All three interfaces are equal citizens. They all talk to the same core, the same database, the same dispatcher. Use whichever fits how you work — or all three.

**Database-as-queue.** The dispatcher polls SQLite directly. No in-memory event bus, no message broker. If the server crashes, you restart and it picks up where it left off. Zero recovery effort.

**Stateless agents.** Every run is a fresh instance. Context comes entirely from the system prompt (agent instructions) and the task's comment thread. No hidden state, no drift.

**OpenRouter for LLMs.** All agent calls route through [OpenRouter](https://openrouter.ai), so you can use any model. Agent runtime is built on [Google ADK](https://google.github.io/adk-docs/) with LiteLLM.

**Real tools.** Agents read files, write files, and run shell commands against your actual codebase. This isn't a sandbox — it's your project directory.

Everything stays local — the database, the workspace, the execution. No cloud dependency.

---

## CLI Reference

### Server

```bash
sabbatical server up                  # start server + dispatcher
sabbatical server status              # task counts, active workers, total cost
sabbatical server down                # graceful shutdown
```

### Organizations

```bash
sabbatical organization create <n> --workspace-path <path> --description "<text>"
sabbatical organization list
sabbatical organization view <n>
sabbatical organization delete <n>
```

### Agents

```bash
sabbatical agent add <n> --organization <org> --instructions <path.md>
sabbatical agent add <n> --organization <org> --instructions <path.md> --boss <boss>
sabbatical agent list --organization <org>
sabbatical agent view <n> --organization <org>
sabbatical agent edit <n> --organization <org> --boss <n>
sabbatical agent remove <n> --organization <org>
```

### Tasks

```bash
sabbatical task create "<title>" --organization <org> --description "<spec>"
sabbatical task list --organization <org> --status <open|in_progress|failed|done|canceled>
sabbatical task view <id>
sabbatical task comment <id> "<message>"
sabbatical task preempt <id>
sabbatical task done <id>
sabbatical task cancel <id>
sabbatical task reopen <id>
```

### Runs

```bash
sabbatical run view <run-id>
sabbatical run list --task <id>
```

---

## Prerequisites

- Python 3.12+
- An [OpenRouter](https://openrouter.ai) API key
- Config auto-generates at `~/.sabbatical/config.toml` on first run

---

## Status

V1 — active development. Core execution model is stable: local multi-agent task collaboration, real tool access, cost tracking. Coming next: context window management (thread summarization), task decomposition primitives, broader LLM provider support.

---

## Contributing

Issues and PRs welcome. If you're building with Sabbatical or have feedback on the collaboration model, [open a discussion](https://github.com/elpapi42/sabbatical/discussions).
