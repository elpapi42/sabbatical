import re
from datetime import datetime, timezone
from pathlib import Path

from strands_tools.file_read import file_read

SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def create_assistant_tools(db, organization_scope=None):
    async def create_organization(
        name: str, workspace_path: str, description: str = ""
    ) -> str:
        """Create a new organization. Use this after the user approves your proposal."""
        if not SNAKE_CASE_RE.match(name):
            return f"Error: name '{name}' must be snake_case"
        if not Path(workspace_path).is_absolute():
            return "Error: workspace_path must be absolute"

        async with db.transaction():
            existing = await db.fetch_one(
                "SELECT name FROM organizations WHERE name = :name", {"name": name}
            )
            if existing:
                return f"Error: Organization '{name}' already exists."

            await db.execute(
                "INSERT INTO organizations (name, description, workspace_path) VALUES (:name, :description, :workspace_path)",
                {
                    "name": name,
                    "description": description,
                    "workspace_path": workspace_path,
                },
            )
            await db.execute(
                "INSERT INTO task_sequences (organization_name, next_number) VALUES (:org, 1)",
                {"org": name},
            )
        return f"Successfully created organization '{name}'"

    async def write_instructions_file(
        name: str, organization: str, content: str
    ) -> str:
        """Generate the .md instructions artifact for an agent.
        Writes to <workspace_path>/.sabbatical/agents/<name>.md
        Returns the absolute path to the generated file."""
        org = await db.fetch_one(
            "SELECT workspace_path FROM organizations WHERE name = :name",
            {"name": organization},
        )
        if not org:
            return f"Error: Organization '{organization}' not found."

        path = Path(org["workspace_path"]) / ".sabbatical" / "agents" / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return str(path)

    async def add_agent(
        name: str,
        organization: str,
        instructions_path: str,
        description: str = "",
        boss: str = "",
        max_iterations: int = 50,
    ) -> str:
        """Add an agent to an organization. Use this after the user approves."""
        if not SNAKE_CASE_RE.match(name):
            return f"Error: name '{name}' must be snake_case"

        async with db.transaction():
            org = await db.fetch_one(
                "SELECT name FROM organizations WHERE name = :org",
                {"org": organization},
            )
            if not org:
                return f"Error: Organization '{organization}' not found."

            existing = await db.fetch_one(
                "SELECT name FROM agents WHERE name = :name AND organization_name = :org",
                {"name": name, "org": organization},
            )
            if existing:
                return f"Error: Agent '{name}' already exists in '{organization}'."

            if boss:
                boss_row = await db.fetch_one(
                    "SELECT name FROM agents WHERE name = :name AND organization_name = :org AND is_removed = 0",
                    {"name": boss, "org": organization},
                )
                if not boss_row:
                    return f"Error: Boss '{boss}' not found in '{organization}'."

            await db.execute(
                """INSERT INTO agents (name, organization_name, description, boss, instructions_path, max_iterations)
                   VALUES (:name, :org, :description, :boss, :path, :max_iter)""",
                {
                    "name": name,
                    "org": organization,
                    "description": description,
                    "boss": boss if boss else None,
                    "path": instructions_path,
                    "max_iter": max_iterations,
                },
            )
        return f"Successfully added agent '{name}' to '{organization}'"

    async def create_task(
        title: str, organization: str, description: str = "", assignee: str = "user"
    ) -> str:
        """Create a task. Use this after the user approves."""
        async with db.transaction():
            org = await db.fetch_one(
                "SELECT name FROM organizations WHERE name = :org",
                {"org": organization},
            )
            if not org:
                return f"Error: Organization '{organization}' not found."

            if assignee != "user":
                agent = await db.fetch_one(
                    "SELECT name FROM agents WHERE name = :name AND organization_name = :org AND is_removed = 0",
                    {"name": assignee, "org": organization},
                )
                if not agent:
                    return f"Error: Agent '{assignee}' not found in '{organization}'."

            await db.execute(
                "UPDATE task_sequences SET next_number = next_number + 1 WHERE organization_name = :org",
                {"org": organization},
            )
            seq = await db.fetch_one(
                "SELECT next_number FROM task_sequences WHERE organization_name = :org",
                {"org": organization},
            )

            # Generate ID
            parts = organization.split("_")
            if len(parts) == 1:
                acronym = organization[:4].upper()
            else:
                acronym = "".join(p[0] for p in parts).upper()
            if len(acronym) < 4:
                acronym = acronym.ljust(4, acronym[-1] if acronym else "X")
            task_id = f"{acronym}-{seq['next_number'] - 1:04d}"

            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            queued_at = now if assignee != "user" else None

            await db.execute(
                """INSERT INTO tasks (id, organization_name, title, description, status, assignee, queued_at, created_at)
                   VALUES (:id, :org, :title, :desc, 'open', :assignee, :queued_at, :now)""",
                {
                    "id": task_id,
                    "org": organization,
                    "title": title,
                    "desc": description or title,
                    "assignee": assignee,
                    "queued_at": queued_at,
                    "now": now,
                },
            )
        return f"Successfully created task {task_id}"

    async def list_agents(organization: str) -> str:
        """List all agents in an organization."""
        rows = await db.fetch_all(
            "SELECT name, description, boss FROM agents WHERE organization_name = :org AND is_removed = 0",
            {"org": organization},
        )
        if not rows:
            return f"No agents found in '{organization}'."
        return "\n".join(
            [
                f"- {r['name']} (Boss: {r['boss'] or 'None'}): {r['description']}"
                for r in rows
            ]
        )

    async def list_tasks(organization: str) -> str:
        """List all tasks in an organization."""
        rows = await db.fetch_all(
            "SELECT id, title, status, assignee FROM tasks WHERE organization_name = :org",
            {"org": organization},
        )
        if not rows:
            return f"No tasks found in '{organization}'."
        return "\n".join(
            [
                f"- {r['id']} ({r['status']}): {r['title']} [Assigned: {r['assignee']}]"
                for r in rows
            ]
        )

    return [
        create_organization,
        write_instructions_file,
        add_agent,
        create_task,
        list_agents,
        list_tasks,
        file_read,
    ]
