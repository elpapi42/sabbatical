# Top 5 Improvements for Sabbatical

A prioritized review of the codebase and specifications, identifying the highest-impact changes needed to make Sabbatical useful for real-world multi-agent orchestration.

---

## 1. Fix `final_text` Accumulation — Routing Is Broken

### Problem

In `src/sabbatical/server/worker.py:83-86`, the agent's final output is captured by overwriting `final_text` on every content event:

```python
if text:
    final_text = text  # overwrites every time
```

If the ADK runner emits the agent's response across multiple events (streaming chunks, reasoning + answer split), the `@tag` can land in an earlier event that gets overwritten. The tag parser then runs on a fragment, misses the tag, and the system escalates to user — breaking the entire multi-agent chain. This already happened in a real test run (see `issues.md` #1).

### Recommended Solution

Accumulate all text across events, then use the full accumulated text for both the comment and tag parsing:

```python
final_text_parts = []
# in the event loop:
if text:
    final_text_parts.append(text)
# after the loop:
final_text = "".join(final_text_parts) if final_text_parts else None
```

Additionally, as a defense-in-depth measure, run the tag parser against the comment that was actually inserted into the database, not the separately-captured variable. This eliminates any divergence between what the thread shows and what the router acts on.

### Justification

Without reliable routing, the entire multi-agent collaboration model collapses. Every chain that hits this bug requires manual user intervention, which defeats the purpose of autonomous orchestration. This is a P0 — the tool's core value proposition doesn't work when this fires.

---

## 2. Context Growth Management — Quadratic Token Costs Will Kill Adoption

### Problem

Two issues compound into one scaling wall. First, agents produce verbose meta-commentary — restating file contents, writing bullet-point summaries of what they did, duplicating information that's already in the workspace. Second, `build_context_payload` injects the *entire* untruncated comment thread into every agent's context (`context_builder.py:147-149`). The result: token consumption grows O(n²) with handoffs. A real 3-agent chain already consumed 670K input tokens. A 6-agent chain would be catastrophic.

### Recommended Solution — Two-Pronged

#### (a) Prompt-level fix (immediate, zero-cost)

Add a "Comment Discipline" section to Block A of `SYSTEM_RULES_TEMPLATE` that explicitly teaches agents how to write concise handoffs:

```
## Comment Discipline

Your message will be injected into every future agent's context. Brevity is a direct cost saving.

- Reference workspace files by path instead of restating their contents.
- Summarize decisions and blockers in 2-3 sentences, not bullet-point inventories.
- Bad: "I created src/api/routes.py with the following endpoints: GET /users (returns all users),
  POST /users (creates a user)..."
- Good: "Created API routes in src/api/routes.py (3 endpoints). See file for details.
  Blocker: auth middleware not yet wired."
```

#### (b) Technical fix (follow-up)

Implement a token budget for Block D. When the comment thread exceeds a configurable threshold (e.g., 4000 tokens), summarize older comments using a cheap/fast model call, keeping only the last 2-3 comments in full. Store the summary as a system comment so it's visible in the timeline. This caps the per-run context at roughly `static_prefix + task_description + summary + recent_comments`.

### Justification

This is the single biggest barrier to real-world use. Even if routing works perfectly, a 5-agent project will burn through budget rapidly. The prompt fix is zero-cost and can ship immediately; the technical fix creates a sustainable ceiling. Together they transform Sabbatical from "works for demos" to "works for real projects."

---

## 3. Implement Cost Tracking — Flying Blind on Spend

### Problem

`openrouter_cost()` in `cost.py:77-79` is a stub returning `0.0`. Every run, session, task, and organization shows `$0.00`. The status dashboard, CLI output, and all cost aggregation functions (`sum_run_costs`, `organization_total_cost`, `system_total_cost`) produce meaningless results. There is zero visibility into actual OpenRouter spend.

### Recommended Solution

OpenRouter returns the actual cost in the `x-openrouter-cost` response header. LiteLLM (which Sabbatical uses via ADK) can surface this. The implementation should:

1. **Capture cost from LiteLLM response metadata.** LiteLLM exposes `response_cost` in its response object or via callbacks. Register a LiteLLM success callback that captures `response._hidden_params` or the response headers and accumulates cost per run.

2. **Fallback: static pricing table.** For cases where the header isn't available, maintain a simple dict of `model → (input_price_per_M, output_price_per_M)` for commonly used models. Imperfect but better than `0.0`.

3. **Store per-run cost in the existing `total_cost` column** — the schema already supports this, it's just never populated with real data.

```python
# In worker.py, after the event loop:
# Option A: parse from LiteLLM response metadata
# Option B: fallback calculation
PRICING = {
    "minimax/minimax-m2.7": (0.50, 1.50),  # per 1M tokens
    "anthropic/claude-sonnet-4": (3.00, 15.00),
    # ...
}

def estimate_cost(model, in_tok, out_tok):
    prices = PRICING.get(model, (0.0, 0.0))
    return (in_tok * prices[0] + out_tok * prices[1]) / 1_000_000
```

### Justification

Cost awareness is existential for an LLM orchestration tool. Users need to know "this 5-agent task cost me $2.40" to make informed decisions about model selection, agent granularity, and iteration limits. Without it, Sabbatical is an open spigot — users will either avoid it out of fear or get surprised by bills. Every other improvement (context reduction, prompt tuning) is also impossible to measure without cost data.

---

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

---

## 5. Expand Agent Tooling — Agents Can't Do Real Software Work Efficiently

### Problem

Agents have exactly four tools: `read_file`, `write_file`, `list_directory`, `run_command` (defined in `src/sabbatical/agent/tools.py`). For any non-trivial software engineering task, this is severely limiting:

- **No search capability.** To find where a function is defined, an agent must `list_directory` recursively, then `read_file` on candidates one by one. This burns 5-10 iterations on what should be a single `grep`. In a codebase with 50+ files, this is untenable.
- **No diff/patch.** To modify a file, the agent must `read_file` the entire thing, then `write_file` the entire thing back. For a 500-line file where the agent changes 3 lines, this wastes output tokens and is error-prone (the model might subtly alter lines it wasn't supposed to touch).
- **No git awareness.** Agents can't check what's changed, create branches, or commit. They operate as if the filesystem is a blank slate, with no awareness of version control.

The fallback is `run_command("grep -r 'pattern' .")` — but that's fragile, requires the agent to know shell syntax, and wastes an iteration on plumbing instead of thinking.

### Recommended Solution

Add purpose-built tools that match how developers actually work:

```python
def search_files(pattern: str, path: str = ".", file_glob: str = "*") -> str:
    """Search file contents for a regex pattern. Returns matching lines with file paths."""

def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replace a specific text span in a file. Safer than rewriting the whole file."""

def git_status() -> str:
    """Show current git status of the workspace."""

def git_diff(path: str = None) -> str:
    """Show uncommitted changes, optionally filtered to a specific file."""
```

These map directly to the agent's system prompt tools list (update Block A to reference the new tools), and they dramatically reduce the iteration count needed for common operations. A `search_files` call replaces 3-5 iterations of list+read. An `edit_file` call replaces a full read+rewrite cycle and eliminates accidental modifications.

### Justification

Iteration count is the primary driver of both cost and quality. Every iteration spent on filesystem plumbing is an iteration *not* spent on reasoning about the actual task. The current 4-tool set forces agents into a pattern where 60-70% of their iterations are navigation overhead. Better tools directly reduce cost (fewer iterations = fewer tokens), improve output quality (agents spend more budget on the actual work), and expand the range of tasks Sabbatical can handle (agents can now work effectively in real codebases, not just toy examples).

---

## Priority Summary

| # | Issue | Type | Effort | Impact |
|---|-------|------|--------|--------|
| 1 | `final_text` fragmentation | Bug fix | Small | Critical — routing breaks entirely |
| 2 | Context growth management | Prompt + architecture | Medium | High — cost/scaling ceiling |
| 3 | Cost tracking | Feature | Medium | High — zero spend visibility |
| 4 | Real-time run observability | Feature | Large | High — UX transformation |
| 5 | Agent tool expansion | Feature | Medium | High — agent efficiency 2-3x |

Items 1-3 are prerequisites for using Sabbatical on real projects. Items 4-5 are what make it a tool people would *choose* to use over running agents manually.
