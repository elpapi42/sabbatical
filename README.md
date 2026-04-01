# Sabbatical

**Stop pair programming with AI. Start managing it.**

---

You open Claude Code. You type a request. You wait. It responds. You react. You wait again. For every task, you're stuck in a synchronous loop — blocked while it works, blocking it while you think.

The workaround? More sessions. You open three Claude Code tabs, four Cursor windows, juggling contexts. Now you're a human load balancer — remembering which session is doing what, re-explaining context when one drifts, copy-pasting results between them. You traded one bottleneck for a coordination problem.

Sabbatical is a different model. You build a team of AI agents once — a lead developer, a backend specialist, a test writer, whatever your project needs. Then you dispatch tasks to them the same way a tech lead assigns tickets. The agents pick up work, collaborate through `@mentions`, hand off between specialists, and surface results when they're done, blocked, or ready for review.

Meanwhile, you're doing what you're actually good at — using Claude Code to plan the next initiative, breaking a complex objective into tasks your team can execute, reviewing a PR from another team, writing a design doc. Your AI tool becomes your thinking partner for planning. Your Sabbatical team handles the execution. You're not context-switching between AI sessions. You're managing a team through tasks.

It's the difference between juggling five chat windows and having a team that works from a backlog. One scales with you. The other scales against you.

**You, in Claude Code:**
```
You:         "Add idempotency keys to the charge endpoint.
              Assign it to the payments team."

Claude Code:  ✅ Task PAYM-0003 created and assigned to lead_dev.
```

You close the tab. You go scope the billing migration.

**Meanwhile, in the background — the Sabbatical task thread:**
```
lead_dev:      Scoped the work. Needs DB migration + handler logic. @backend_dev
backend_dev:   Added idempotency_keys table, wrapped /charges POST
               in key check. @test_writer
test_writer:   Tests passing for duplicate charge rejection
               and key expiry. @lead_dev
lead_dev:      Reviewed. Ship it. @user
```

**20 minutes later, back in Claude Code:**
```
You:         "What's the status on the payments team?"

Claude Code:  PAYM-0003 "Add idempotency keys" — ✅ done.
              4 agent handoffs · 5 files changed · all tests passing.
```

Three agents. Zero interruptions. You were working on something else the whole time.

---

## Use It Your Way

Sabbatical isn't a new tool competing for your attention. It's infrastructure you control from wherever you already work.

**From your AI tool.** Claude Code, Codex, Gemini, Cursor, Windsurf — anything that speaks MCP. Your AI tool becomes the manager: it builds orgs, dispatches tasks, monitors progress, and intervenes when agents get stuck. You stay in one place and talk in natural language.

**From the CLI.** If you live in the terminal, the full-featured CLI gives you direct control over every operation — organizations, agents, tasks, runs. No middleman.

**From anything you build.** Sabbatical exposes a complete HTTP REST API. Build a TUI, a web dashboard, an IDE extension — whatever fits your workflow. The API covers every operation available in the CLI and MCP server, so nothing is off-limits.

All three interfaces talk to the same core, the same database, the same dispatcher. Mix and match as you like.

---

## Quick Start

### Install and start

```bash
pipx install sabbatical
export OPENROUTER_API_KEY="sk-or-your-key"
sabbatical api up
```

The API server starts in the background. The dispatcher daemon starts automatically and begins polling for queued tasks. Check that everything is running:

```bash
sabbatical status
```

### Connect your AI tool

**Claude Code:**
```bash
claude mcp add sabbatical -- sabbatical mcp
```

**Cursor, Windsurf, or any MCP client:**
```json
{
  "mcpServers": {
    "sabbatical": {
      "command": "sabbatical",
      "args": ["mcp"]
    }
  }
}
```

Your AI tool now has 22 MCP operations to build teams, dispatch tasks, and monitor agents. The skill files are automatically installed to `~/.sabbatical/skill/` on first run. To install them into a specific project directory instead:

```bash
sabbatical install-skill --path ./your-project
```

For Claude Code, add this to your `CLAUDE.md`:

```
## Sabbatical — AI Agent Orchestration

Sabbatical is installed and available for managing teams of AI agents that execute work autonomously.

Read and follow the instructions in ~/.sabbatical/skill/SKILL.md for using Sabbatical.

Key concepts:
- "Organization" / "team" / "squad" = a Sabbatical organization — a group of agents scoped to a codebase.
- "Agent" / "specialist" / "dev" = a Sabbatical agent — a stateless AI worker defined by an instructions file.
- "Task" / "ticket" / "issue" / "work item" = a Sabbatical task — a unit of work dispatched to an organization.
- "Assign to the team" / "hand this off" / "dispatch this" = create a task in the relevant organization.
- "Check on" / "status" / "how's it going" = list or view tasks to report progress.

When the user talks about assigning work, creating tasks, checking progress, building teams,
or managing agents — use the Sabbatical MCP tools. Match informal language to the right operation.
```

### Build your first team

Organizations map to real team boundaries — a backend platform team, a payments squad, a mobile client team — each scoped to a codebase directory.

```bash
sabbatical organization create payments \
  --workspace-path /absolute/path/to/payments-service \
  --description "Payments service team — API, billing logic, Stripe integration"

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

### Dispatch your first task

```bash
sabbatical task create "Add idempotency keys to charge endpoint" \
  --organization payments \
  --description "Wrap the /charges POST handler in idempotency logic..."
```

The task auto-assigns to `lead_dev` (the root agent) and enters the dispatch queue. Agents start collaborating immediately. Check back later:

```bash
sabbatical task list --organization payments
sabbatical task view PAYM-0001
```

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

And here's the workflow that makes it click: use your current AI tool — Claude Code, Codex, Gemini, whatever — for what it's great at: **planning**. Talk through the problem, break a complex objective into smaller tasks, write detailed specs. Then offload the execution to your Sabbatical organization. Your AI tool thinks with you. Your agents do the work. Planning stays interactive. Execution runs in the background.

---

## Cheaper Models, Same Quality

Orchestrating a team of specialized agents comes with a bonus you might not expect: **you can get away with cheaper models.**

A single agent working alone needs to be smart enough to handle everything — architecture decisions, implementation details, edge cases, testing. That demands a flagship model. But a team of agents acts as its own safety net. The lead reviews the backend dev's work. The test writer catches what the implementer missed. Given clear instructions and enough context in the thread, agents on smaller models course-correct each other — and the final output holds up to the quality you'd expect from models that cost 10x more.

The team structure isn't just an organizational tool. It's a cost multiplier.

---

## How It Works

At the center is a **core library** — organizations, agents, tasks, the dispatcher, the execution engine. On top of it, three interfaces serve different users:

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

**Agents are stateless.** Every run is a fresh instance. Context comes from the agent's instructions file and the task's comment thread — no hidden state, no drift between runs.

**Agents collaborate through `@mentions`.** When an agent finishes, the system reads the last valid `@tag` from its last comment and routes the task to that agent (or `@user`). No workflow engine, no DAG — just a comment thread and a handoff protocol.

**The thread is a safety net.** If an agent's last comment has no valid tag, the system scans the thread for agents who were mentioned but haven't run since their mention, and routes to the most recently mentioned one. If no candidates remain, it escalates to the agent's boss, then to you.

**Everything runs locally.** SQLite database, local file access, shell commands against your actual codebase. No cloud dependency. All LLM calls route through [OpenRouter](https://openrouter.ai), so you pick the model.

For the full picture, see [Architecture](docs/architecture.md) and [Core Concepts](docs/concepts.md).

---

## Documentation

| Document | What it covers |
|----------|----------------|
| [Core Concepts](docs/concepts.md) | Organizations, agents, tasks, runs, comments, and the collaboration model |
| [Architecture](docs/architecture.md) | System design, component structure, and key design decisions |
| [Task Lifecycle](docs/task-lifecycle.md) | State machine, transitions, routing rules, failure modes, and crash recovery |
| [Agent Execution](docs/agent-execution.md) | Runtime, tools, context building, and the worker model |
| [Dispatcher](docs/dispatcher.md) | Polling loop, concurrency control, heartbeats, and daemon management |
| [Configuration](docs/configuration.md) | All config options, model selection, and tuning tips |
| [CLI Reference](docs/cli-reference.md) | Complete reference for all CLI commands |
| [API Reference](docs/api-reference.md) | Complete reference for all REST API endpoints |
| [MCP Reference](docs/mcp-reference.md) | Complete reference for all MCP server tools |

---

## Prerequisites

- Python 3.12+
- An [OpenRouter](https://openrouter.ai) API key

## Contributing

Issues and PRs welcome. If you're building with Sabbatical or have feedback on the collaboration model, [open a discussion](https://github.com/elpapi42/sabbatical/discussions).
