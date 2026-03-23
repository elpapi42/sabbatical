# The Assistant — Conversational Copilot

## 1. Core Vision & Operational Boundaries
* **The Conversational Copilot:** The Assistant's primary purpose is to help the user plan work, act as a sounding board for design decisions, translate plans into meaningful tasks, and assign those tasks intelligently to the right agents.
* **Strict Non-Execution:** The Assistant never executes technical work. It is entirely distinct from the stateless Agents, which are the autonomous workers defined by a specific System Prompt and a shared, static tool set.
* **Runs on the API Server:** The Assistant runs within the API Server process and is exposed to the CLI via a dedicated streaming endpoint. All state modifications requested by The Assistant are executed by the API Server through the same state store operations as the manual CLI commands.

---

## 2. Session Management
All interactions with The Assistant are encapsulated within persistent **Sessions** (see Data Model spec for entity fields).

* **Disposability & Persistence:** Sessions are inherently disposable. Users can create a new session on demand, leaving old sessions behind without cluttering their active workspace. However, because sessions are persistent in the local database, historical sessions can be retrieved, reviewed, and seamlessly resumed at any time.
* **Scoped Context:** When the user opens a session with `--organization <organization_name>`, The Assistant receives context about the specified organization's agents, hierarchy, and active tasks, enabling it to make informed suggestions.

---

## 3. Project Planning & Task Delegation (Primary Capability)
The core reason The Assistant exists is to bridge the gap between a human's high-level intent and the concrete, atomic tasks required by stateless agents. 

* **Strategic Planning:** The Assistant helps the user think through design decisions, architectural choices, and project roadmaps. It acts as a sounding board before any technical work begins.
* **Task Breakdown:** Once a plan is agreed upon, the Assistant breaks the work down into logical, atomic tasks.
* **Spec Generation:** For each task, the Assistant writes comprehensive, highly detailed task descriptions (specs) that provide clear instructions for the worker agents.
* **Intelligent Assignment:** Utilizing the scoped organization's context (when the session is launched with `--organization`), The Assistant assigns tasks to the most appropriate agent in the roster based on their persona, expertise, and position in the hierarchy.
* **Database Population:** After proposing the tasks and receiving user approval, The Assistant creates the task records in the database via the API Server, setting the correct `assignee`.

---

## 4. Organization Bootstrapping (Secondary Capability)
While users have full manual control via CLI commands to create organizations and add agents, The Assistant also serves as an organizational designer to minimize friction when starting a new project.

* **Prompt-to-Tree Generation:** Users can provide a high-level goal to The Assistant (e.g., *"I need an agent organization to build a React frontend with a Node backend"*), and it will generate a complete proposed hierarchical tree.
* **Proposal & Approval:** The user must approve or tweak the proposed tree in the chat before any permanent changes are made.
* **Database Persistence:** Once the user approves the structure, The Assistant uses the `write_instructions_file` tool to generate the `.md` instruction artifacts, then calls `add_agent` to populate the global database.
* **Manual CLI Fallbacks:** All conversational planning and bootstrapping features are optional. Users maintain full manual control via CLI commands.

---

## 5. Communication Protocol
* **Streaming Endpoint:** The API Server exposes a dedicated SSE (Server-Sent Events) streaming endpoint for The Assistant. The CLI connects to this endpoint to pipe live token generation to the terminal.
* **LLM Provider:** The Assistant's LLM calls are routed through the OpenRouter API, using the model configured in `~/.sabbatical/`.

---

## 6. Chat TUI Design (V1)

The chat interface is a minimal, readline-style TUI built with `prompt_toolkit`. It provides a streaming conversational experience without the complexity of a full terminal UI framework.

### Layout

```
╭─ Sabbatical Assistant ─ Session: CHAT-abc123 ─ Org: react_app ──╮
│                                                                    │
│  you: Let's add a dark mode toggle to the header.                   │
│                                                                    │
│  assistant: Good idea. Here is the plan:                           │
│  1. Task: Update Tailwind config for dark mode (assigned to        │
│     `css_specialist`).                                             │
│  2. Task: Build the ThemeToggle React component (assigned to       │
│     `frontend_dev`).                                               │
│                                                                    │
│  Shall I create these tasks?                                       │
│                                                                    │
│  you: yes, go ahead                                                │
│                                                                    │
│  assistant: Done! Created tasks REAC-0004 and REAC-0005.  │
│                                                                    │
╰────────────────────────────────────────────────────────────────────╯
 > _
```

### Components

* **Header bar** — Displays session ID and organization scope (if any). Static, single line at the top.
* **Conversation pane** — Scrollable history of the conversation. Messages are prefixed with `assistant:` or `you:`. Assistant messages stream in token-by-token as they arrive via SSE.
* **Input prompt** — A `> ` prompt at the bottom where the user types their message. Supports standard readline keybindings (arrow keys, Ctrl+A/E, history with up/down).

### Interaction Flow

1. User types a message and presses Enter.
2. The input prompt is disabled (shows `...` or a spinner) while the Assistant is responding.
3. Tokens stream in from the SSE endpoint and are appended to the conversation pane in real time.
4. When the `done` SSE event arrives, the input prompt is re-enabled.
5. If the Assistant calls a tool (e.g., `create_organization`), a brief status line appears: `[Creating organization 'react_app'...]`. The tool result is not displayed — only the Assistant's natural language response summarizing what happened.

### Session Resume

When `chat resume <session_id>` is invoked, the CLI fetches the full session transcript from `GET /api/sessions/:id` and pre-populates the conversation pane with the historical messages before re-enabling the input prompt.

### Exit

* `exit`, `quit`, or `Ctrl+D` — Gracefully ends the session. The session persists in the database and can be resumed later.
* `Ctrl+C` — If the Assistant is mid-response, cancels the current streaming response and re-enables the input prompt. If the prompt is idle, exits the session.

### Dependencies

`prompt_toolkit` is added to the project dependencies for input handling, history, and basic terminal rendering.

---

## 7. Limitations
* **No Active Dispatching:** The Assistant does not route tasks or manage handoffs.
* **No Technical Execution:** The Assistant never executes code, modifies files, or runs terminal commands.
