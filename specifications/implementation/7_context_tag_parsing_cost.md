# Implementation: Context Tag Parsing Cost

## 11. Context Builder

### `server/context_builder.py`

Builds the 4-block prompt payload defined in the Context Management spec. Blocks A-C form the system prompt (static prefix); Block D forms the user message (dynamic suffix).

```python
async def build_context_payload(db, config, agent, task, comments, org_name):
    """Returns (system_prompt: str, user_message: types.Content)."""

    # ── Block A: System Rules & Protocol ──
    block_a = SYSTEM_RULES_TEMPLATE  # Constant string: handoff protocol, execution
                                      # constraints, formatting rules

    # ── Block B: Organization Topology ──
    org_row = await fetch_organization(db, org_name)
    agents = await fetch_active_agents(db, org_name)
    tree_text = render_hierarchy_tree(agents)  # Renders each agent as "name — description"
    block_b = f"""## Organization: {org_name}
Purpose: {org_row['description'] or 'Not specified'}

### Agent Roster
{tree_text}
"""

    # ── Block C: Agent Profile ──
    instructions = Path(agent["instructions_path"]).read_text()
    boss_text = f"Your Boss: @{agent['boss']}" if agent["boss"] else "You are a root agent (no Boss)."
    subordinates = await fetch_subordinates(db, org_name, agent["name"])
    sub_text = ", ".join(f"@{s['name']}" for s in subordinates) if subordinates else "None"
    block_c = f"""## Your Identity: {agent['name']}
{boss_text}
Your Subordinates: {sub_text}
Max Iterations: {agent['max_iterations']}

{instructions}
"""

    system_prompt = f"{block_a}\n\n{block_b}\n\n{block_c}"

    # ── Block D: Task State & Comments (Dynamic Suffix) ──
    comment_thread = "\n\n".join(
        f"**{c['author']}** ({c['created_at']}):\n{c['body']}"
        for c in comments
    )
    block_d = f"""## Current Task
ID: {task['id']}
Organization: {org_name}
Title: {task['title']}

### Description
{task['description']}

### Comment Thread
{comment_thread if comment_thread else '(No comments yet)'}

---
You are now executing this task. Do your work using the available tools, then write your final output.
"""

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=block_d)],
    )

    return system_prompt, user_message
```

---

## 12. Tag Parser

### `server/tag_parser.py`

```python
import re

TAG_PATTERN = re.compile(r"@([a-z][a-z0-9_]*)\b")

def parse_first_tag(text: str) -> str | None:
    """Extract the first valid @tag from text. Returns the name without @, or None."""
    match = TAG_PATTERN.search(text)
    return match.group(1) if match else None
```

The `@user` literal is also matched by this pattern (since `user` matches `[a-z][a-z0-9_]*`). The caller distinguishes `user` from agent names.

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

