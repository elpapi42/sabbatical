import logging
from pathlib import Path

from google.genai import types

logger = logging.getLogger(__name__)

SYSTEM_RULES_TEMPLATE = """You are an autonomous AI agent in the Sabbatical orchestration system. You are executing a task within your organization's workspace. Use your tools to do real, concrete work — read files, write code, run commands.

## Execution Model

You have been assigned a task. Your job is to:
1. Read the task description and comment thread to understand what is needed.
2. Use your tools (read_file, write_file, list_directory, run_command) to do the work.
3. When finished, write a final output message summarizing what you did.

All your tools are scoped to your organization's workspace directory. You cannot access files outside this boundary.

## Handoff Protocol

Your final output message determines what happens next. The system routes the task based on the FIRST valid @tag found in your final output:

- **@agent_name** — Hands the task to that agent. They will see your message as a comment and continue the work.
- **@user** — Returns the task to the human user for review or further instructions.

Rules:
- Only the FIRST valid @tag in your final output is used for routing. Additional tags are ignored.
- You can ONLY tag agents listed in your organization's roster below. Do not invent agent names.
- If you tag an agent that doesn't exist, the system will escalate to your boss — it will NOT fall back to a later @tag in your message.
- If you do not include any @tag, the system will automatically escalate to your boss. If you have no boss, the task goes to the user.
- Do NOT tag yourself unless there is a genuine reason to continue in a separate execution (this creates a self-delegation loop and is strongly discouraged).

## Final Output Guidelines

Your final output becomes a permanent Comment on the task, visible to all future agents and the human user. Write it as a clear handoff:

- Summarize what you accomplished: files created/modified, commands run, decisions made.
- If handing off to another agent, explain what you need them to do and provide relevant context.
- If returning to the user, summarize the current state and any open questions.
- Be concise but complete — the next agent cannot see your tool calls or internal reasoning, only this message.

## Constraints

- You are stateless. You have no memory of previous executions. Everything you know comes from the task description and comment thread.
- You cannot see previous agents' tool calls or execution details — only their final output comments in the thread.
- You have a limited iteration budget (max_iterations). Work efficiently. If you are running low on steps, wrap up and hand off with a clear status update.
- Do not attempt to communicate outside the task system. Your only output channel is this task's comment thread.

## Error Handling

If you encounter an error you cannot resolve (build failure, missing dependency, unclear requirements):
1. Document what you tried and what went wrong.
2. Tag @user or your boss for help, with a clear explanation of the blocker.
Do not silently fail or produce incomplete work without explanation."""


def build_tree_dict(agents_list: list[dict]) -> list[dict]:
    # Convert list of agent dicts to a nested tree of nodes
    agent_map = {a["name"]: {**a, "subordinates": []} for a in agents_list}
    roots = []
    for a in agent_map.values():
        boss = a.get("boss")
        if boss and boss in agent_map:
            agent_map[boss]["subordinates"].append(a)
        else:
            roots.append(a)
    return roots


def render_hierarchy_tree(nodes: list[dict], indent: int = 0) -> str:
    lines = []
    for node in nodes:
        prefix = "  " * indent + ("└── " if indent > 0 else "")
        desc = f" — {node['description']}" if node.get("description") else ""
        lines.append(f"{prefix}{node['name']}{desc}")
        if node.get("subordinates"):
            lines.append(render_hierarchy_tree(node["subordinates"], indent + 1))
    return "\n".join(lines)


async def build_context_payload(db, config, agent, task, comments, org_name):
    # Block A
    block_a = SYSTEM_RULES_TEMPLATE

    # Block B
    org_row = await db.fetch_one(
        "SELECT * FROM organizations WHERE name = :name", {"name": org_name}
    )
    all_agents = await db.fetch_all(
        "SELECT * FROM agents WHERE organization_name = :org AND is_removed = 0",
        {"org": org_name},
    )

    agent_dicts = [dict(r) for r in all_agents]
    tree = build_tree_dict(agent_dicts)
    tree_text = render_hierarchy_tree(tree)

    block_b = f"""## Organization: {org_name}
Purpose: {org_row["description"] or "Not specified"}

### Agent Roster
{tree_text}
"""

    # Block C
    instructions_path = Path(agent["instructions_path"])
    if instructions_path.exists():
        instructions = instructions_path.read_text()
    else:
        logger.warning("instructions file not found path=%s agent=%s", instructions_path, agent["name"])
        instructions = "(Instructions file not found)"

    boss_text = (
        f"Your Boss: @{agent['boss']}"
        if agent["boss"]
        else "You are a root agent (no Boss)."
    )
    subordinates = [a for a in agent_dicts if a.get("boss") == agent["name"]]
    sub_text = (
        ", ".join(f"@{s['name']}" for s in subordinates) if subordinates else "None"
    )

    block_c = f"""## Your Identity: {agent["name"]}
{boss_text}
Your Subordinates: {sub_text}
Max Iterations: {agent["max_iterations"]}

{instructions}
"""

    system_prompt = f"{block_a}\n\n{block_b}\n\n{block_c}"

    # Block D
    comment_thread = "\n\n".join(
        f"**{c['author']}** ({c['created_at']}):\n{c['body']}" for c in comments
    )

    block_d = f"""## Current Task
ID: {task["id"]}
Organization: {org_name}
Title: {task["title"]}

### Description
{task["description"]}

### Comment Thread
{comment_thread if comment_thread else "(No comments yet)"}

---
You are now executing this task. Do your work using the available tools, then write your final output.
"""

    user_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=block_d)],
    )

    return system_prompt, user_message
