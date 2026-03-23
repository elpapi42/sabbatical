# Sabbatical

Sabbatical is a developer-centric CLI tool for orchestrating specialized organizations of AI agents. It operates on a Client-Server architecture running locally on your machine: a centralized, always-on Local API Server handles orchestration, state, and agent execution, while a Thin CLI acts as the human interface.

## Prerequisites

- **Python 3.12+**
- **Poetry** (Dependency management)

## 1. Setup & Installation

Clone the repository and install the dependencies using Poetry:

```bash
git clone git@github.com:elpapi42/sabbatical.git
cd sabbatical
poetry install
```

## 2. Configuration & Environment

The application relies on OpenRouter to connect to LLMs. You must set your OpenRouter API key in your environment or directly in the configuration file.

The global configuration file will be automatically generated at `~/.sabbatical/config.toml` the first time you run the server or any CLI command.

To set your key beforehand:
```bash
export OPENROUTER_API_KEY="sk-or-your-key-here"
```

If you need to change the default LLM models or concurrency limits, you can manually edit `~/.sabbatical/config.toml`.

## 3. Database & Migrations

Sabbatical uses a local SQLite database (`~/.sabbatical/sabbatical.db`) with Alembic for schema migrations.

**Automatic Migrations:**
When you start the server using `sabbatical server up`, the system will automatically run `alembic upgrade head` to apply any pending database migrations or create the initial database if it doesn't exist.

**Manual Migrations (For Development):**
If you are developing and changing the database schema (`src/sabbatical/db.py`), you need to generate a new migration:

```bash
# Autogenerate a new migration based on changes to db.py
poetry run alembic revision --autogenerate -m "description_of_change"

# Manually upgrade the database
poetry run alembic upgrade head
```

## 4. Running the Server

Sabbatical operates using a background server that manages the database queue and agent worker threads.

To start the server:
```bash
poetry run sabbatical server up
```
*This starts the API server and the dispatcher loop in the background. It will print the PID and port.*

To check the server status:
```bash
poetry run sabbatical server status
```

To stop the server gracefully (allowing active worker threads to finish their current API calls):
```bash
poetry run sabbatical server down
```

## 5. Quick Start: CLI Workflow

Once the server is running, you interact with the system entirely via the CLI.

### Option A: The Assistant (Conversational Copilot)
The easiest way to bootstrap an organization and start creating tasks is to use the conversational Assistant:

```bash
# Start a new chat session to plan your project
poetry run sabbatical chat new
```

### Option B: Manual Setup
You can also manually build your organization, add agents, and create tasks:

**1. Create an Organization:**
```bash
poetry run sabbatical organization create my_project --workspace-path /absolute/path/to/project --description "My awesome project"
```

**2. Add Agents:**
You must provide a `.md` file with the agent's prompt/instructions.
```bash
poetry run sabbatical agent add lead_dev --organization my_project --instructions ./prompts/lead.md
poetry run sabbatical agent add ui_dev --organization my_project --boss lead_dev --instructions ./prompts/ui.md
```

**3. Create a Task:**
By default, tasks are assigned to `user` (you) until you delegate them.
```bash
poetry run sabbatical task create "Build a login page" --organization my_project
```

**4. Delegate & Comment:**
To trigger the agent worker, mention their `@name` in a comment. The dispatcher will instantly pick it up.
```bash
poetry run sabbatical task comment MYPR-0000 "@lead_dev please review the requirements and start building."
```

**5. View Task Progress:**
Check the full history of the task, including agent comments and execution runs:
```bash
poetry run sabbatical task view MYPR-0000
```
