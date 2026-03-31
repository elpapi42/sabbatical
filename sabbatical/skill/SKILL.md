---
name: sabbatical
description: Orchestrate autonomous AI agents via Sabbatical. Use when the user wants to delegate work to AI agents, create/manage agent teams, track tasks, or monitor agent execution. Always use the MCP server tools — never the CLI or HTTP API directly.
compatibility: Requires the Sabbatical MCP server to be connected (tool names like get_status, create_task, etc. must be available).
metadata:
  author: elpapi42
---

You have access to **sabbatical**, a local AI agent orchestration system. Use it to delegate work to autonomous AI agents that collaborate through an append-only task system.

## Critical Rule

**Always use MCP tools.** You have direct access to MCP tools (`get_status`, `create_task`, `add_comment`, etc.). Never use the CLI (`sabbatical` command) or HTTP API (`curl`, `requests`) — the MCP tools are always available and preferred.

## Quick Start

```
1. get_status()                          # confirm server is up
2. create_organization(name, workspace_path)
3. create_agent(organization, name, instructions_path)   # root agent (no boss)
4. create_task(title, organization, description)         # auto-queued to root agent
```

The dispatcher picks up queued tasks automatically — no manual trigger needed.

## Key Concepts

See [references/concepts.md](references/concepts.md) for full details on:
- Organizations, Agents, Tasks, Runs, Comments, Timeline
- Task IDs and status lifecycle
- Comment routing with `@mentions`
- Agent hierarchy and boss/subordinate relationships

## MCP Tools Reference

See [references/mcp-tools.md](references/mcp-tools.md) for the complete tool list with parameters and return shapes.

## Common Workflows

See [references/workflows.md](references/workflows.md) for step-by-step patterns:
- Set up a new project
- Monitor and inspect tasks
- Intervene on a running or failed task
- Clean up completed work

## Decision Guide

| What you want | Tool to use |
|---|---|
| Check if server is running | `get_status` |
| See all projects | `list_organizations` |
| Delegate work to agents | `create_task` |
| Steer a task to a specific agent | `add_comment` with `@agent_name` |
| Stop a running task | `preempt_task` |
| Retry a failed task | `retry_task` |
| Mark user-assigned task done | `complete_task` |
| See what an agent did | `get_run` |
