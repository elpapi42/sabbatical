# Sabbatical — Product Vision & System Summary

## 1. What is Sabbatical?
Sabbatical is a developer-centric tool for orchestrating specialized organizations of AI agents. It operates on a Client-Server architecture running locally on the developer's machine: a centralized, always-on **Local API Server** handles orchestration, state, and agent execution, while a **Thin CLI** and a **Web Application** act as human interfaces over HTTP. A conversational copilot ("**The Assistant**") helps users plan work, make design decisions, break down projects into tasks, and optionally bootstrap organizations.

## 2. Core Concepts

* **Organizations** — User-defined clusters of Agents grouped for a specific project, each confined to a `workspace_path` directory on the host machine. Organizations are fully isolated — agents in different organizations cannot interact. Within an organization, agents can organically form sub-groups through the Boss/subordinate hierarchy; these emergent "teams" are not a formal entity but arise naturally from how the hierarchy is structured.
* **Agents** — Stateless worker profiles defined by an instructions file (`.md`). Each agent belongs to an organization, has an optional Boss reference (forming an informational hierarchy), and a configurable `max_iterations` iteration limit. All agents share a static, hardcoded tool set. Agent names must be `snake_case`. Agents are soft-deleted (marked as removed but preserved for historical reference).
* **Tasks** — The fundamental unit of work, identified by organization-prefixed IDs (e.g., `REAC-0012`). A task has a `description` (the detailed spec) separate from its `title`. Tasks track collaboration via **Comments** (human messages, agent final outputs, system notes) and **Runs** (granular execution details). These are separate database entities.
* **Runs** — A first-class entity representing a single, contiguous block of agent execution on a task. Runs encapsulate tool calls, internal reasoning, and raw stdout/stderr. Only the agent's final output surfaces as a Comment. Runs are never included in the agent context payload.
* **Sessions** — Persistent, resumable chat conversations with The Assistant, encapsulating the full transcript and cost telemetry.
* **The Dispatcher** — A continuous polling loop inside the API Server that monitors the database for dispatchable tasks, claims them atomically, and spins up worker threads. It uses a **database-as-a-queue** model — there is no in-memory event bus.
* **The Assistant** — A conversational copilot whose primary job is project planning, breaking down work into tasks, writing detailed specs, and assigning work to appropriate agents. It can also bootstrap organizations. It never executes technical work and is entirely distinct from Agents.

## 3. Key Design Decisions

* **Tag-Based Delegation** — Agents collaborate by `@` tagging peers in their final output. The Dispatcher routes based on the first valid tag found (the "First Tag Rule"). There is no task decomposition or sub-tasking — all collaboration happens within a single task's comment thread, ensuring shared context.
* **Database-as-a-Queue** — The Dispatcher polls the database on a continuous loop rather than relying on an in-memory event bus. Tasks are queued by a `queued_at` timestamp and claimed atomically. This eliminates dropped events on crashes and simplifies recovery to zero-effort — on startup, the Dispatcher simply resumes polling.
* **Informational Hierarchy** — Boss/subordinate relationships guide but do not constrain routing. Agents can tag any peer in the same organization. Hierarchy powers smart escalation: if an agent fails to route, the Dispatcher escalates to its Boss (or to the user for root agents).
* **Self-Tagging** — Allowed but not promoted. Agent prompts should discourage unnecessary self-delegation loops.
* **Organization Isolation** — No cross-organization coordination mechanism. Agents can only tag agents in the same organization.
* **Comments Only in Context** — Agents see only the task's Comments, not Run execution details. This keeps context lean and cost-effective.
* **No Retries** — Any LLM or system failure immediately transitions the task to `failed`. The user must manually recover.
* **No File Conflict Resolution (V1)** — Concurrent agents in the same organization may edit the same files. Last write wins.
* **FIFO Dispatch** — Tasks are dispatched in first-in, first-out order by `queued_at` timestamp, subject to a configurable max concurrency limit.
* **Task Immutability** — Task records are never deleted from the database (except when an entire organization is deleted, which cascades to all associated data).
* **Agent Soft-Delete** — Agents are never hard-deleted individually. Removing an agent marks it as removed, preserving its record for historical reference. Subordinates are promoted to root.
* **Naming Convention** — Organization and agent names must be `snake_case`.
* **Cost from Runs** — The Run is the sole unit of cost. All aggregate cost and token figures (organization, agent, task) are computed at query time by summing across relevant Runs, not stored redundantly.
* **Auto-Assignment to Root Agent** — When a task is created, it is automatically assigned to the organization's root agent (the agent with no Boss) and queued for dispatch. There is no option to create a task assigned to `user` — all tasks immediately enter the dispatch queue.
* **OpenRouter Only (V1)** — All LLM calls route through the OpenRouter API (via `LiteLlm` from Google's Agent Development Kit for framework integration).
* **Configuration** — Global config lives in `~/.sabbatical/config.toml` (API keys, model selection, concurrency limits, server settings).

## 4. Reading Guide

| Spec | Answers |
|---|---|
| [Architecture](2_architecture.md) | How is the system built? Components, protocols, infrastructure. |
| [Data Model](3_data_model.md) | What are the entities, fields, and relationships? |
| [Task Lifecycle](4_task_lifecycle.md) | How do tasks flow? State machine, handoffs, routing, invariants. |
| [Context Management](5_context_management.md) | What do agents see? Prompt caching strategy. |
| [The Assistant](6_the_assistant.md) | What does the conversational copilot do? |
| [CLI Commands](7_cli_commands.md) | How do I use it? Complete command reference. |
| [API Endpoints](8_api_endpoints.md) | What are the HTTP endpoints? Request/response formats. |
| [System Prompts](9_prompts.md) | What do agents and the Assistant see? Exact prompt definitions. |
| [Web Application](10_web_app.md) | How does the browser-based UI work? Pages, components, real-time updates. |
