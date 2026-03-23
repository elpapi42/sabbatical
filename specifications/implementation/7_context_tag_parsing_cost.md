# Implementation: Context Tag Parsing Cost

## 11. Context Builder

### `server/context_builder.py`

Builds the 4-block prompt payload defined in the Context Management spec. Blocks A-C form the system prompt (static prefix); Block D forms the user message (dynamic suffix).

```python
async def build_context_payload(db, config, agent, task, comments, org_name):
    """Returns (system_prompt: str, user_message: types.Content)."""

    # ── Block A: System Rules & Protocol ──
    block_a = SYSTEM_RULES_TEMPLATE  # Constant string: how Sabbatical works, private
                                      # work / public voice, handoff protocol,
                                      # iteration budget, error handling

    # ── Block B: Organization Topology ──
    org_row = await fetch_organization(db, org_name)
    agents = await fetch_active_agents(db, org_name)
    tree_text = render_hierarchy_tree(agents)  # Renders each agent as "name — description"
    block_b = f"""## Organization: {org_name}
Purpose: {org_row['description'] or 'Not specified'}

### Agent Roster
{tree_text}
"""

    # ── Block C: Agent Identity & Place in Organization ──
    instructions = Path(agent["instructions_path"]).read_text()
    boss_text = f"Your Boss: @{agent['boss']}" if agent["boss"] else "You are a root agent (no Boss)."
    subordinates = await fetch_subordinates(db, org_name, agent["name"])
    sub_text = ", ".join(f"@{s['name']}" for s in subordinates) if subordinates else "None"
    block_c = f"""---

## You Are: {agent['name']}

{instructions}

---

## Your Place in the Organization

{boss_text}
Your Direct Reports: {sub_text}

Hierarchy is informational, not restrictive. You may tag any agent in the roster — but your Boss is your default escalation path, and your direct reports are your natural delegates. Use this structure to guide your routing decisions.

**Iteration budget for this run: {agent['max_iterations']} turns.** Work efficiently.
"""

    system_prompt = f"{block_a}\n\n{block_b}\n\n{block_c}"

    # ── Block D: Task Briefing (Dynamic Suffix) ──
    comment_thread = "\n\n".join(
        f"**{c['author']}** ({c['created_at']}):\n{c['body']}"
        for c in comments
    )
    block_d = f"""---

## Task Briefing

**{task['id']} — {task['title']}**
Organization: {org_name}

### What Needs to Be Done

{task['description']}

### Thread — Team History on This Task

{comment_thread if comment_thread else '(This task has just been opened. You are the first to work on it.)'}

---

This thread is now yours to advance. Do your work, then write your message to the team. Your message becomes the next comment in this thread — address it clearly, summarize what you accomplished, and include an @tag to route the task to whoever should go next.
"""

    user_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=block_d)],
    )

    return system_prompt, user_message
```

---

## 12. Tag Parser — "First Valid Tag" Algorithm

### `server/tag_parser.py`

The tag parser implements a multi-pass extraction algorithm to find the first **valid** routing target in a block of text. This makes routing fault-tolerant against LLM hallucinations and typos.

```python
import re

TAG_PATTERN = re.compile(r"@([a-z][a-z0-9_]*)\b")

def extract_all_tags(text: str) -> list[str]:
    """Extract all @tag candidates from text in order of appearance."""
    return TAG_PATTERN.findall(text)

def resolve_first_valid_tag(text: str, valid_names: set[str]) -> tuple[str | None, list[str]]:
    """Extract all tags, then return the first one in valid_names.
    Returns (first_valid_tag_or_None, all_extracted_tags)."""
    all_tags = extract_all_tags(text)
    for tag in all_tags:
        if tag in valid_names:
            return tag, all_tags
    return None, all_tags
```

The `valid_names` set is built by the caller: `{active agent names in org} | {"user"}`. The regex only matches lowercase snake_case identifiers, matching the agent naming convention.

### Algorithm Steps
1. **Extraction:** Regex extracts every `@tag` candidate, preserving chronological order.
2. **Validation:** Each candidate is checked against the organization's active roster + the reserved `"user"` literal. Invalid tags (hallucinated names, typos, removed agents) are skipped.
3. **Selection:** The first valid tag is selected for routing.

### Caller Behavior
The two-element return allows callers to distinguish three states:
- `(tag, [...])` — Valid tag found, route to it.
- `(None, [some, tags])` — Tags present but none valid.
  - **Agent output:** Escalate to boss or user.
  - **User comment:** Return 404 error (user gets feedback).
- `(None, [])` — No tags at all.
  - **Agent output:** Escalate to boss or user.
  - **User comment:** Append comment with no state change.

### Multi-Tag Warning (Agent Output)
When an agent's final output contains multiple valid tags, the system routes to the first valid tag and inserts a system comment: `[SYSTEM: Multiple valid tags detected in output. Only @first was used. Ignored: @second, @third]`. This aids debugging when agents violate the single-tag rule.

### Edge Cases
- **Typo + valid fallback:** `@front_end_devv please fix this, or @user take a look.` → `@front_end_devv` is invalid (not in roster), skipped. `@user` is valid, task routes to user.
- **All invalid:** `@ghost_agent do something` → No valid tag. Agent output: escalate. User comment: 404.
- **Multiple valid:** `@database_agent setup the schema, then @backend_dev build the routes.` → Routes to `@database_agent`, ignores `@backend_dev`, inserts warning comment.

---

## 13. Cost Helpers

### `server/cost.py`

```python
import databases

async def sum_run_costs(db: databases.Database, **filters) -> dict:
    """Sum consumed tokens and cost across Runs matching the given filters.

    Supported filter keys: organization_name, agent_name, task_id.
    """
    where_clauses = []
    values = {}
    for key, value in filters.items():
        where_clauses.append(f"{key} = :{key}")
        values[key] = value

    where = " AND ".join(where_clauses) if where_clauses else "1=1"

    row = await db.fetch_one(
        query=f"""
            SELECT COALESCE(SUM(consumed_input_tokens), 0) as input_tokens,
                   COALESCE(SUM(consumed_output_tokens), 0) as output_tokens,
                   COALESCE(SUM(total_cost), 0.0) as cost
            FROM runs
            WHERE {where}
        """,
        values=values,
    )

    return {
        "consumed_input_tokens": row["input_tokens"],
        "consumed_output_tokens": row["output_tokens"],
        "total_cost": row["cost"],
    }


async def organization_total_cost(db: databases.Database, org_name: str) -> dict:
    """Total cost for an organization: all Runs + scoped Sessions."""
    runs = await sum_run_costs(db, organization_name=org_name)
    session_row = await db.fetch_one(
        query="""
            SELECT COALESCE(SUM(consumed_input_tokens), 0) as input_tokens,
                   COALESCE(SUM(consumed_output_tokens), 0) as output_tokens,
                   COALESCE(SUM(total_cost), 0.0) as cost
            FROM sessions
            WHERE organization_scope = :org_name
        """,
        values={"org_name": org_name},
    )

    return {
        "consumed_input_tokens": runs["consumed_input_tokens"] + session_row["input_tokens"],
        "consumed_output_tokens": runs["consumed_output_tokens"] + session_row["output_tokens"],
        "total_cost": runs["total_cost"] + session_row["cost"],
    }


async def system_total_cost(db: databases.Database) -> dict:
    """Total cost across all Runs + all Sessions."""
    runs = await sum_run_costs(db)
    session_row = await db.fetch_one(
        query="""
            SELECT COALESCE(SUM(consumed_input_tokens), 0) as input_tokens,
                   COALESCE(SUM(consumed_output_tokens), 0) as output_tokens,
                   COALESCE(SUM(total_cost), 0.0) as cost
            FROM sessions
        """
    )

    return {
        "consumed_input_tokens": runs["consumed_input_tokens"] + session_row["input_tokens"],
        "consumed_output_tokens": runs["consumed_output_tokens"] + session_row["output_tokens"],
        "total_cost": runs["total_cost"] + session_row["cost"],
    }


def openrouter_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost from OpenRouter pricing.

    V1: Uses a static price table. Future: parse cost from OpenRouter response headers.
    """
    # TODO: Cost tracking will be designed later. For now, this is a placeholder.
    # OpenRouter returns cost in x-openrouter-cost header; prefer that when available.
    # V1: Uses a static price table. Future: parse cost from OpenRouter response headers.
    return 0.0
```

---

