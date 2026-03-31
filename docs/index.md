# Sabbatical Documentation

**Stop pair programming with AI. Start managing it.**

Sabbatical is a local AI agent orchestration platform for developers. Instead of juggling multiple interactive AI chat sessions, you build a team of specialized agents, dispatch tasks to them through a backlog, and let them collaborate asynchronously while you focus on higher-level work.

## How It Works

1. **Build a team** - Create an organization with specialized agents (lead developer, backend specialist, test writer, etc.), each defined by a markdown instructions file.
2. **Dispatch tasks** - Create tasks and assign them to the team. Agents pick up work automatically.
3. **Agents collaborate** - Agents hand off work to each other using `@mentions` in a shared comment thread. No workflow engine, no DAG - just natural conversation.
4. **Review results** - Check task status, read the comment thread, review execution details, and provide feedback when agents need human input.

## Quick Start

### Install

```bash
pipx install sabbatical
```

### Configure

```bash
export OPENROUTER_API_KEY="sk-or-your-key"
```

On first run, Sabbatical creates a default configuration at `~/.sabbatical/config.toml`. See [Configuration](configuration.md) for all options.

### Start the System

```bash
sabbatical api up
```

This starts the API server. The dispatcher daemon starts automatically and begins polling for queued tasks.

### Connect Your AI Tool

Sabbatical exposes an MCP server so AI tools can manage your teams directly:

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

### Build a Team

```bash
sabbatical organization create payments \
  --workspace-path /path/to/payments-service \
  --description "Payments service team"

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

### Dispatch Work

```bash
sabbatical task create "Add idempotency keys to charge endpoint" \
  --organization payments \
  --description "Wrap the /charges POST handler in idempotency logic..."
```

The task is automatically assigned to the organization's root agent and queued for execution.

### Monitor Progress

```bash
sabbatical status                     # system overview
sabbatical task list --organization payments
sabbatical task view PAYM-0001        # full timeline
sabbatical run view <run-id>          # execution details
```

## Documentation

| Document | Description |
|----------|-------------|
| [Core Concepts](concepts.md) | Organizations, agents, tasks, runs, comments, and the collaboration model |
| [Architecture](architecture.md) | System design, component overview, and key design decisions |
| [Task Lifecycle](task-lifecycle.md) | Task states, transitions, routing, and the dispatch loop |
| [Agent Execution](agent-execution.md) | How agents run, their tools, context building, and the worker model |
| [Dispatcher](dispatcher.md) | The polling loop, concurrency control, crash recovery, and daemon management |
| [Configuration](configuration.md) | All configuration options and the config file format |
| [CLI Reference](cli-reference.md) | Complete reference for all CLI commands |
| [API Reference](api-reference.md) | Complete reference for all REST API endpoints |
| [MCP Reference](mcp-reference.md) | Complete reference for all MCP server tools |

## Prerequisites

- Python 3.12+
- An [OpenRouter](https://openrouter.ai) API key
- SQLite (bundled with Python)

## Project Links

- Repository: https://github.com/elpapi42/sabbatical
- Issues: https://github.com/elpapi42/sabbatical/issues
