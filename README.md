# Sabbatical

**A local AI agent orchestration system built around async task collaboration — not chat sessions.**

---

Most people use AI by opening a chat window, typing a request, and waiting. The AI responds. You react. It's a conversation — synchronous, serial, one thing at a time. You're blocked until it finishes, and it's blocked until you respond.

Sabbatical is a different model. You write a task spec. You assign it to an agent. The agent picks it up, does the work using real tools in your actual codebase, hands it off to another agent via an `@mention`, and those agents keep working until the task surfaces back to you — done, blocked, or ready for review. Meanwhile, you're working on something else.

It's the difference between pair programming on a video call and managing a team through tasks. The team model scales. The call doesn't.

---

## How It Works

Sabbatical runs a **local API server** on your machine. The server manages a **database-as-queue**: it continuously polls for tasks assigned to agents, spins up worker threads, runs agents against real tools (file reads, file writes, shell commands), and processes their output. There is no cloud dependency. Everything — the database, the agent workspace, the execution — lives on your machine.

### The Core Concepts

**Organizations** are isolated workspaces. Each organization has a `workspace_path` (a directory on your machine) and a roster of agents. Agents in different organizations cannot interact.

**Agents** are stateless worker profiles defined by a `.md` instruction file. The instruction file is the agent's identity: its expertise, its working style, its persona. Agents don't persist state between executions — their only context is the task description and the comment thread.

**Tasks** are the unit of work. Each task has a title, a detailed description (the spec), a status, an assignee, and a **comment thread**. The thread is the shared memory of the task: every agent that works on it leaves a comment, and every future agent reads the full thread before picking up where the previous one left off.

**The Comment Thread** is what makes multi-agent collaboration coherent. Agents can't see each other's internal reasoning or tool calls — those are private to each run. But they see every comment in the thread. When an agent hands off to another with `@agent_name`, the next agent receives the full thread context including that handoff message. No context is lost between agents.

**The Dispatcher** is the always-on polling loop that drives everything. It claims dispatchable tasks atomically (preventing double-execution), spins up a worker thread per task, and processes the agent's final output to determine routing. It runs inside the API server — `server up` starts it, `server down` gracefully stops it.

### The Handoff Protocol

When an agent finishes its work, it writes a final message. That message becomes a permanent comment on the task thread. The system reads the **first valid `@tag`** in that message to determine where the task goes next:

- `@agent_name` → task is routed to that agent, queued for dispatch
- `@user` → task returns to you for review or input
- No valid tag → task escalates to the agent's boss; if no boss, it goes to you

This is how agents collaborate without you in the loop. A `lead_dev` agent can delegate a specific problem to a `frontend_dev`, who can hand the result back to `lead_dev` for review, who can then return it to `@user`. Three agents, zero interruptions for you.

### The Hierarchy

Agents can have a **boss** — another agent in the same organization. The hierarchy is informational, not restrictive: any agent can tag any other agent in the organization. But the hierarchy powers smart escalation: if an agent fails to route properly (no valid tag in its output), the dispatcher automatically escalates to its boss. This gives you a safety net and a natural review chain.

---

## A Real Workflow

You're building a React app. You have an organization `react_app` with three agents: `lead_dev` (root), `frontend_dev` (reports to `lead_dev`), and `test_writer` (reports to `lead_dev`).

You write a task spec and kick it off:

```bash
sabbatical task create "Add dark mode toggle to the header" \
  --organization react_app \
  --description "Implement a dark/light mode toggle in the header component. Use Tailwind's dark: prefix classes. The toggle should persist preference in localStorage. Existing header is at src/components/Header.tsx." \
  --assign lead_dev
```

`lead_dev` picks it up. It reads the spec, inspects the codebase with `read_file` and `list_directory`, and decides this is UI work for `frontend_dev`. It writes a detailed handoff comment explaining the approach and tags `@frontend_dev`. You're not involved.

`frontend_dev` picks up the task. It reads the thread — including `lead_dev`'s briefing — modifies `Header.tsx`, adds a `ThemeToggle` component, and updates the Tailwind config. It finishes and tags `@test_writer` with a summary of what was changed.

`test_writer` reads the thread, understands the full context of what was built, and writes tests for the toggle behavior. It tags `@lead_dev` for a final review pass.

`lead_dev` reviews everything, requests a small change via a comment, tags `@frontend_dev` again. `frontend_dev` makes the fix, tags `@lead_dev`. `lead_dev` approves and tags `@user`.

You get a notification. You check the thread with `task view`, see the full history of what every agent did, review the code changes in your editor, and run `task done REAC-0012`.

While all of that was happening, you were working on three other tasks.

---

## The Assistant

Sabbatical includes a conversational planning copilot — **The Assistant** — for when you want help structuring work before delegating it.

```bash
sabbatical chat new --organization react_app
```

The Assistant knows your organization's agents and hierarchy. It helps you break down high-level goals into atomic tasks, writes detailed task specs that stateless agents can execute without ambiguity, and assigns tasks to the right agents. It can also bootstrap entire organizations from scratch — proposing agent names, hierarchies, and instruction files — if you're starting a new project.

The Assistant never executes technical work. It is a planning layer, not a worker. Workers are agents.

---

## Setup

### Prerequisites

- Python 3.12+
- Poetry
- An [OpenRouter](https://openrouter.ai) API key (Open to contributions to make more providers available, even Claude Code, Codex, Gemini adapters)

### Install

```bash
git clone https://github.com/elpapi42/sabbatical.git
cd sabbatical
poetry install
```

### Configure

```bash
export OPENROUTER_API_KEY="sk-or-your-key-here"
```

The config file is auto-generated at `~/.sabbatical/config.toml` on first run. Edit it to change the default model, concurrency limit, or server port.

### Start the Server

```bash
poetry run sabbatical server up
```

The server starts in the background. The dispatcher begins polling immediately. Any tasks already queued in the database from a previous session are picked up automatically.

```bash
poetry run sabbatical server status   # snapshot: task counts, active workers, total cost
poetry run sabbatical server down     # graceful shutdown; active runs finish before stopping
```

---

## CLI Reference

### Organizations

```bash
sabbatical organization create <name> --workspace-path <path> --description "<text>"
sabbatical organization list
sabbatical organization view <name>       # hierarchy tree
sabbatical organization delete <name>     # cascade deletes all agents, tasks, runs
```

### Agents

```bash
sabbatical agent add <name> --organization <org> --instructions <path.md>
sabbatical agent add <name> --organization <org> --instructions <path.md> --boss <boss_name> --description "<one-liner>"
sabbatical agent list --organization <org>
sabbatical agent view <name> --organization <org>
sabbatical agent edit <name> --organization <org> --boss <name>
sabbatical agent remove <name> --organization <org>   # soft-delete; history preserved
```

### Tasks

```bash
sabbatical task create "<title>" --organization <org> --assign <agent|user> --description "<spec>"
sabbatical task list --organization <org> --status <open|in_progress|failed|done|canceled>
sabbatical task view <id>                    # full thread: comments + run summaries interleaved
sabbatical task comment <id> "<message>"     # @mention an agent to delegate/unblock
sabbatical task preempt <id>                 # interrupt an in-progress task
sabbatical task done <id>                    # you verify and close
sabbatical task cancel <id>
sabbatical task reopen <id>
```

### Runs

```bash
sabbatical run view <run-id>           # full step-by-step: tool calls, arguments, stdout/stderr
sabbatical run list --task <id>
```

### Chat (The Assistant)

```bash
sabbatical chat new [--organization <org>]
sabbatical chat list
sabbatical chat resume <session-id>
```

---

## Writing Agent Instructions

An agent's identity lives in a `.md` file referenced by `--instructions`. This file is its character sheet: who it is, what it knows, how it works. Write it as if describing a real team member.

```markdown
# lead_dev

You are the lead developer for this project. You own overall code quality and architecture decisions.

When a task comes to you, your first job is to understand the full scope, then either execute it yourself or break it into focused sub-problems and delegate to the right specialist on your team.

Your team:
- @frontend_dev — React, TypeScript, UI/UX
- @test_writer — unit tests, integration tests, coverage

When delegating, write a clear briefing in your handoff: what you've already done, what you need from them, and any constraints or decisions they should know about. The next agent's only context is this thread.
```

The instruction file is injected into every run as part of the agent's context. Keep it specific. Generic instructions produce generic agents.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Local API Server                   │
│                                                     │
│  ┌─────────────┐    ┌────────────────────────────┐  │
│  │  Dispatcher │    │     Worker Threads         │  │
│  │  (polling   │───▶│  Agent + ADK Runner        │  │
│  │   loop)     │    │  Tools: read/write/shell   │  │
│  └─────────────┘    └────────────────────────────┘  │
│         │                       │                   │
│         ▼                       ▼                   │
│  ┌──────────────────────────────────────────────┐   │
│  │              SQLite Database                 │   │
│  │  organizations · agents · tasks · comments   │   │
│  │  runs · sessions                             │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
              ▲
              │ HTTP
              ▼
        ┌──────────┐
        │ Thin CLI │  (sabbatical <command>)
        └──────────┘
```

- **Database-as-queue**: no in-memory event bus. The dispatcher polls SQLite directly. Crash recovery is zero-effort — on `server up`, the dispatcher resumes polling and picks up any open tasks.
- **LLM provider**: all calls route through [OpenRouter](https://openrouter.ai), giving you access to any model.
- **Agent runtime**: built on [Google ADK](https://google.github.io/adk-docs/) with LiteLLM for model routing.
- **Stateless workers**: each run is a fresh agent instance. Context is injected entirely through the system prompt and the task thread.

---

## Development

```bash
# Generate a new DB migration after changing the schema
poetry run alembic revision --autogenerate -m "describe_the_change"

# Apply migrations manually
poetry run alembic upgrade head
```

Migrations run automatically on `server up`. The database lives at `~/.sabbatical/sabbatical.db`.

---

## Status

Sabbatical is under active development. V1 is focused on establishing the core execution model: local multi-agent task collaboration with a stable state machine, real tool access, and cost tracking. Planned for future iterations: context window management (thread summarization), richer task decomposition primitives, and broader LLM provider support.

---

## Contributing

Issues and PRs are welcome. If you're building something with Sabbatical or have feedback on the agent collaboration model, open a discussion.
