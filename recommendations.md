## 4. Add Real-Time Run Observability — The Execution Black Box

### Problem

When a task is dispatched, the user gets zero feedback until the run completes. An agent might run for 2-5 minutes doing tool calls, reading files, writing code — and the user sees nothing. The only interface is `task view` (which shows the timeline *after* completion) and `run view` (which shows execution steps *after* completion). There's no way to watch progress, spot a stuck agent, or intervene before tokens are wasted.

This is especially painful because:
- If an agent goes off-track (wrong approach, hallucinating, stuck in a loop), the user doesn't know until it finishes and the tokens are already burned.
- The existing `preempt` command is a blunt tool — you can kill a run, but you can't know whether you *should* until it's too late.

### Recommended Solution

Add an SSE (Server-Sent Events) streaming endpoint for active runs:

```
GET /api/runs/{id}/stream  →  SSE stream of execution events
```

The worker already processes events in a loop (`worker.py:78-121`). Augment this to publish events to an in-memory broadcast channel (e.g., `asyncio.Queue` per active run). The SSE endpoint subscribes to this channel. Events would include:

- `tool_call`: tool name + arguments (not full output, to keep it light)
- `llm_step`: iteration count / budget remaining
- `progress`: periodic heartbeat with token count so far

On the CLI side, add `sabbatical run watch <run_id>` or `sabbatical task watch <task_id>` that connects to the SSE stream and renders a live view. Even a simple scrolling log of `Step 3: read_file(src/main.py) ... Step 4: write_file(src/api.py) ... Step 5: run_command(pytest)` would be transformative.

### Justification

Observability is the difference between a tool you trust and a tool you tolerate. Every orchestration system (Kubernetes, CI/CD, even `make`) provides real-time feedback. Without it, users can't develop intuition about agent behavior, can't debug bad outcomes, and can't justify the cost. This also directly supports the preemption feature — if you can *see* an agent going wrong, `preempt` becomes a useful tool instead of a panic button.
