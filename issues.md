Critical Issues

### 1. Routing broke — architect's `@developer` tag was not detected

The architect's run ended with `@developer` in its output, but the system logged `[SYSTEM: No valid tag detected. Assigning to user.]`. This required manual user intervention to continue the chain.

**Root cause:** The `final_text` capture in `worker.py:83-86` is fragile:

```python
if event.content and event.content.parts:
    text = "".join(p.text for p in event.content.parts if p.text)
    if text:
        final_text = text  # overwrites every time
```

This keeps only the text from the **last event** that had content. If the ADK runner emits the agent's output across multiple events (e.g., a reasoning event followed by a final-answer event, or the @tag lands in a separate streaming chunk), the `@developer` tag may end up in an earlier event that gets overwritten. The comment we see in the timeline is the `final_text` that was stored — but there's a race between what gets captured as `final_text` and what gets inserted as the comment. The tag parser runs on `final_text`, not on the full accumulated output.

**Fix:** Accumulate all text across events instead of overwriting, or parse the tag from the comment that was actually inserted.

### 2. Cost tracking is completely broken

Every run shows `"cost": 0.0` despite consuming **670K input tokens** and **26K output tokens**. The `openrouter_cost()` function is a stub that returns `0.0`:

```python
def openrouter_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    return 0.0
```

You're flying blind on spend. With 670K tokens through OpenRouter, this task probably cost $1-5+ depending on model, and you have zero visibility into it. This should either parse the `X-OpenRouter-Cost` response header from the LLM call or maintain a pricing lookup table.

---

## Major Issues

### 3. Quadratic token growth from unbounded comment threads

Each agent dumps its **entire summary** into a comment. The architect's comment alone is ~400 words of bullet points. Every subsequent agent receives ALL previous comments in its context via `build_context_payload`:

```python
comment_thread = "\n\n".join(
    f"**{c['author']}** ({c['created_at']}):\n{c['body']}" for c in comments
)
```

This means:
- product_manager gets: task description
- architect gets: task description + product_manager's full output
- developer gets: task description + product_manager's output + architect's output + system comments

Token consumption grows roughly **O(n^2)** with the number of handoffs. For a 3-agent chain this is already 670K tokens. A 6-agent chain would be ruinous.

**Fix:** Either summarize/truncate earlier comments, or teach agents to write to workspace files and keep comments short (just status + file references).

### 4. Agents produce verbose meta-commentary instead of referencing artifacts

The architect's comment contains a massive "Summary of What Was Added" with section headers and bullets — essentially restating what's in the file it wrote. This is wasteful because:
- It bloats the comment thread (see issue #3)
- The next agent has to read the actual file anyway to do real work
- It's duplicated information

The system prompt says "Be concise but complete" but doesn't enforce brevity or encourage referencing workspace files by path. A better handoff would be: *"Wrote architect section to `reports/match-service.md` (sections 2.1-2.7). @developer please add the Implementation section."*

### 5. Preempted runs waste all their tokens with no recovery

The architect's first run (`17dd24fceb7d`) ran for 141 seconds, was preempted by server shutdown, and all work was lost. The second run started from scratch, re-reading the same files and re-doing the same analysis. There's no checkpoint/resume mechanism.

For the graceful shutdown path, the dispatcher could at least let the current iteration complete before cancelling — or save the agent's partial output as a comment so the next run has context about what was already attempted.

### 6. Dispatcher only picks up one task per poll cycle

`_poll_once` fetches `LIMIT 1` and returns. If `max_concurrency` is 3 and there are 3 queued tasks, it takes 3 poll cycles (3 * polling_interval) to pick them all up. Should fetch `min(available_slots, queued_tasks)` in one pass.

---

## Moderate Issues

### 7. `parse_first_tag` is positionally fragile

The regex matches the **first** `@tag` in the entire text. If an agent writes *"As @user requested, I'm handing off to @developer"*, it routes to `user` instead of `developer`. The system prompt warns about this, but LLMs are bad at following this constraint consistently.

Better approach: look for the **last** `@tag`, or require a structured format like a `## Handoff` section at the end.

### 8. No validation that the task description is coherent with the agent's capabilities

The task description mentions "Three.js" — the developer agent correctly noted *"Three.js is not applicable (it's a 3D graphics library)"*. This means the task description had incorrect/confusing information that wasted agent cycles figuring that out. There's no pre-flight validation or task template system.

### 9. Graceful shutdown doesn't preserve assignee

When the server shuts down, `_graceful_shutdown` sets all in-progress tasks back to `status='open'` but **doesn't set the assignee**. The task keeps its current assignee (the agent), so the dispatcher picks it right back up on restart. This is actually correct behavior — but the system comment `[SYSTEM: Server shutdown. Task suspended.]` is misleading since the task auto-resumes.

However, there's a subtlety: the preempted run's partial work isn't captured, so the agent starts completely fresh. The system comment should at least note this: *"Task suspended. Agent will restart from scratch on server restart."*

### 10. `handle_routing` has heavy code duplication

Lines 262-336 have 4 branches that repeat the same insert-comment + update-task pattern with slight variations. This makes it easy to introduce inconsistencies when modifying routing logic.

---

## Minor Issues

### 11. `sum_run_costs` uses dynamic column names in WHERE clause

```python
where_clauses.append(f"{key} = :{key}")
```

The `key` comes from `**filters` kwargs, which are internal callers — so it's not a SQL injection risk today. But it's a pattern that could become dangerous if exposed more broadly.

### 12. No deduplication guard on dispatcher pickup

If `_poll_once` runs twice before the first worker starts (unlikely but possible under load), the same task could be picked up twice. The `status='in_progress'` UPDATE happens inside the transaction, which should prevent this with SQLite's locking — but there's no explicit `WHERE status='open'` on the UPDATE to make it truly idempotent.

### 13. Iteration counting is confusing

`iteration_count` increments per event with `usage_metadata`, and `max_iterations` is checked per-event. But this counts LLM round-trips, not "iterations" in the user-intuitive sense. The naming could mislead when configuring agents.

---

## Summary: Top 5 Things I'd Fix First

| Priority | Issue | Impact |
|----------|-------|--------|
| 1 | **Fix `final_text` accumulation** — accumulate across events, don't overwrite | Routing failures break the entire multi-agent chain |
| 2 | **Implement `openrouter_cost`** — parse header or pricing table | Zero cost visibility on real spend |
| 3 | **Truncate/summarize comment context** — cap tokens or use workspace file references | Token cost grows quadratically with handoffs |
| 4 | **Teach agents to write short handoffs** — update system prompt to enforce concise comments with file path references | Reduces bloat, improves handoff clarity |
| 5 | **Batch task pickup** — fetch multiple tasks per poll cycle | Latency reduction for concurrent workloads |

Want me to start implementing any of these?
