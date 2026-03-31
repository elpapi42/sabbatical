# Agent Execution

This document covers how agents execute work: the runtime, tools, context building, and the worker model.

## Runtime

Sabbatical uses [Google ADK](https://google.github.io/adk-docs/) (Agent Development Kit) as the agent runtime. LLM calls are routed through OpenRouter via ADK's LiteLLM adapter.

When the dispatcher claims a task, it spawns a worker coroutine that:

1. Loads the agent, task, comments, and organization from the database.
2. Builds the context payload (system prompt + user message).
3. Creates an ADK runner with the agent's tools.
4. Iterates over runner events, recording steps and flushing comments.
5. After completion, applies routing based on the agent's final comment.

## Context Payload

The context is assembled in four blocks, structured to maximize LLM prompt caching.

### Block A: System Rules (Static)

A fixed template injected into every agent's system prompt. It covers:
- How the comment thread works
- Private vs. public work (tool calls are private, comments are public)
- Available tools and their usage
- The `add_comment` protocol (intermediate vs. final)
- Handoff rules (`@tag` routing)
- Comment formatting guidelines (plain prose, no headers, no markdown formatting beyond lists and code blocks)
- Iteration budget awareness
- Error handling instructions (document blockers, escalate)

This block is identical across all agents and runs.

### Block B: Organization Topology (Static per org)

Injected for organizational awareness:
- Organization name and description/purpose
- Agent roster rendered as a hierarchical ASCII tree showing names and descriptions

```
lead_dev — Lead developer, owns code quality and architecture
├── backend_dev — Backend Python specialist, APIs and database
└── test_writer — Testing specialist, unit and integration tests
```

### Block C: Agent Identity (Static per agent)

The agent's specific profile:
- Agent name
- Full instructions content (read from the instructions file)
- Boss and direct reports
- Guidance to delegate to subordinates and escalate to boss
- Workspace path
- Iteration budget for this run

### Block D: Task Briefing (Dynamic)

The only part that changes per task:
- Task ID, title, and organization
- Full task description
- Comment thread history (all comments chronologically, with author and timestamp)
- Instructions to act and post a final comment with `@tag`

**Caching benefit**: Blocks A-C form a stable prefix that LLM providers can cache across runs. Block D at the bottom ensures the cache stays valid even as the task evolves.

## Tools

### Workspace Tools

All workspace tools are sandboxed to the organization's workspace directory. Path validation ensures no file operations can escape the workspace boundary.

#### file_read

Read files from the workspace with multiple modes:

| Mode | Parameters | Description |
|------|-----------|-------------|
| `view` | `path` | Display full file content with line numbers. If path is a directory, lists entries. |
| `lines` | `path`, `start_line`, `end_line` | Show a line range (1-indexed). |
| `search` | `path`, `search_pattern` | Search for a regex pattern. If path is a directory, searches recursively. Uses `grep -rn`. |
| `find` | `path` | List files and directories recursively (up to 200 entries). |

#### file_write

Write content to a file. Creates parent directories if needed. Returns the byte count written.

#### editor

Make targeted edits without rewriting entire files:

| Command | Parameters | Description |
|---------|-----------|-------------|
| `str_replace` | `path`, `old_str`, `new_str` | Replace `old_str` with `new_str`. `old_str` must appear exactly once. |
| `insert` | `path`, `new_str`, `line` | Insert text at a specific line number (1-indexed). |
| `undo_edit` | `path` | Revert the last edit to this file. Only one level of undo is supported. |

The editor maintains an in-memory undo history per file path within a single run.

#### shell

Execute a shell command in the workspace directory:
- Default timeout: 120 seconds
- Returns stdout, stderr (prefixed with `[stderr]`), and exit code
- Runs with `shell=True` for full shell syntax support

### Communication Tool

#### add_comment

The only way agents can write to the task's comment thread:

- **`is_final=false`** (default): Posts an intermediate note. The agent continues working. Tags in intermediate comments are informational only - they don't trigger routing. Use for sharing progress, findings, and decisions.
- **`is_final=true`**: Posts the final message, triggers routing, and ends execution. Must contain exactly one valid `@tag`. Can only be called once with `is_final=true`.

**Validation on final comments**:
- Must contain at least one valid `@tag` (agent name from the roster or `user`).
- Must contain exactly one valid `@tag` (multiple valid tags are rejected).
- If tags are present but none are valid, returns an error listing valid targets.
- If no tags at all, returns an error listing valid targets.

Comments are queued in `thread_state` and flushed to the database by the worker event loop after each LLM event.

## Worker Lifecycle

### Setup Phase

1. Load agent, task, comments, and organization records from the database.
2. Validate that the workspace directory exists.
3. Build the context payload via `build_context_payload()`.
4. Determine the model (agent-specific override or system default).
5. Build the set of valid routing targets (all active agent names + "user").
6. Create the ADK runner with tools and initial heartbeat.

### Execution Loop

The worker iterates over ADK runner events:

1. **LLM reasoning**: Extract text from event content parts. Record as an `llm_reasoning` step.
2. **Tool calls**: Extract function calls. Record each as a `tool_call` step with tool name and arguments.
3. **Comment flushing**: Check `thread_state` for pending `add_comment` calls. Flush intermediate comments to the database. Capture final comment text if submitted.
4. **Token counting**: Aggregate input and output tokens from `usage_metadata`.
5. **Heartbeat**: Update `last_heartbeat` on the run record. Check `cancel_requested` flag.
6. **Iteration limit**: If `iteration_count >= max_iterations`, raise `MaxIterationsExceeded`.

Steps are flushed to the database after each step, enabling real-time progress visibility.

### Completion

On successful completion:

1. Record `final_output` step if the agent submitted a final comment.
2. Compute cost via `openrouter_cost()` (uses LiteLLM pricing tables).
3. Update run: `status='success'`, fill token counts, cost, and execution steps.
4. Call `handle_routing()` to route the task based on `@tag` in the final comment.

### Error Handling

| Error | Run Status | Task Status | System Comment |
|-------|-----------|-------------|----------------|
| `MaxIterationsExceeded` | `failed` | `failed` | Max iterations reached (N) |
| `RunTimedOut` | `failed` | `failed` | Timeout message with duration |
| `CancelledError` | `preempted` | unchanged (already handled by preempt/cancel) | - |
| Generic exception | `failed` | `failed` | Sanitized error message |

Error sanitization converts technical errors into user-friendly messages:
- Context window / token errors -> "Context window exceeded"
- 429 / rate limit -> "LLM rate limit reached"
- Connection / network errors -> "Network error"
- Others -> First 120 chars with pointer to `run view`

### Heartbeat and Cancellation

Every event triggers `_heartbeat_and_check_cancel()`:
1. Updates `last_heartbeat` to current UTC time.
2. Reads `cancel_requested` from the database.
3. If `cancel_requested` is set, raises `asyncio.CancelledError`.

This enables:
- **Liveness detection**: The dispatcher identifies orphaned workers (heartbeat > 60s stale) and marks them as failed.
- **Cooperative cancellation**: User preemption and dispatcher shutdown set the flag; workers check it on every event and self-terminate cleanly.

## Cost Computation

Cost is computed using LiteLLM's `cost_per_token()` function:

```python
cost = openrouter_cost(model, input_tokens, output_tokens)
```

If the model isn't in LiteLLM's pricing table, cost defaults to 0.0. Costs are stored per run and aggregated at query time for tasks, agents, organizations, and the system.

## Model Selection

The model used for a run is determined by:

1. **Agent-specific model** (if set via `agent edit --model`): Takes priority.
2. **System default** (`config.llm.default_model`): Falls back to this if the agent has no override.

The default model is `minimax/minimax-m2.7`. Models are specified in OpenRouter format (e.g., `anthropic/claude-3-5-sonnet-20241022`).
