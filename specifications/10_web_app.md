# Web Application

## 1. Product Overview

### 1.1 What Is the Web App?
The Sabbatical Web Application is a browser-based graphical interface for the Sabbatical AI agent orchestration system. It is the **second client** to the existing Local API Server (running on `localhost:7420`), complementing the Thin CLI. Both clients are equals — they talk to the same REST API, share the same state store, and have full feature parity.

### 1.2 Why It Exists
The CLI excels at rapid, scriptable operations but falls short for:
- **Monitoring**: Watching task progress, run execution, and cost accumulation across an entire system at a glance.
- **Exploration**: Navigating organizational hierarchies, reading task timelines, and drilling into run execution steps.
- **Rich Interaction**: Composing comments with @-mention autocomplete, streaming chat with The Assistant, and inspecting deeply nested data.

The web app provides a persistent, visual, always-open dashboard that makes the system's state immediately legible.

### 1.3 Relationship to CLI
The web app is **not a replacement** for the CLI. It is a complementary view. Both clients:
- Hit the same API endpoints (documented in the API Endpoints spec).
- Perform zero direct database writes.
- Are stateless clients with no server-side session affinity.

The CLI retains exclusive access to `server up`, `server down`, and `server logs` (process lifecycle commands). The web app does not expose shutdown or log-tailing functionality.

### 1.4 Scope
The web app covers all public API endpoints except `POST /api/shutdown`. Every CLI command that maps to an API call has a web equivalent.

---

## 2. Tech Stack

| Concern | Choice | Rationale |
|---|---|---|
| Framework | React 19 + Vite | Fast builds, mature ecosystem, component model fits the hierarchical UI. No SSR needed (purely local). |
| Language | TypeScript (strict mode) | Type safety across API responses and component props. |
| Routing | React Router v7 | Client-side routing with URL-driven views. |
| Styling | Tailwind CSS v4 | Utility-first, rapid iteration, consistent design tokens. |
| State Management | TanStack Query (React Query) v5 | Server-state caching, automatic refetching (polling), optimistic updates, stale-while-revalidate. |
| SSE Client | Native `EventSource` / `fetch` with `ReadableStream` | Minimal dependency; the Assistant streaming endpoint uses standard SSE. |
| Icons | Lucide React | Lightweight, consistent icon set. |
| Markdown Rendering | `react-markdown` + `remark-gfm` | Agent and assistant outputs often contain Markdown. |
| Code Highlighting | `shiki` | Syntax highlighting for code blocks in run execution steps and agent output. |
| Tree Visualization | Custom component (CSS-only) | The agent hierarchy is shallow enough that a library is unnecessary. |
| Package Manager | npm | Standard, no special requirements. |
| Testing | Vitest + React Testing Library | Aligned with Vite ecosystem. |

### 2.1 Non-Choices
- **No Next.js/SSR**: The app runs locally against `localhost`. Server-side rendering provides no benefit and adds complexity.
- **No global state library (Redux, Zustand)**: TanStack Query handles all server state. The minimal client-only state (sidebar open/closed, active filters) lives in URL params or `useState`.
- **No component library (shadcn, MUI)**: Tailwind utilities plus a small set of custom components provide full control without dependency weight. If development velocity demands it, `shadcn/ui` (Radix primitives + Tailwind) is the recommended upgrade path.

---

## 3. Application Structure

### 3.1 Page Map & URL Routing

| URL Pattern | View | Description |
|---|---|---|
| `/` | Dashboard | System-wide status, task counts, cost, active workers. |
| `/organizations` | Organization List | All organizations with cost and agent count. |
| `/organizations/:name` | Organization Detail | Agent hierarchy tree, cost breakdown, task summary. |
| `/organizations/:name/agents/:agentName` | Agent Detail | Instructions, subordinates, cost, model. |
| `/tasks` | Task List | Filterable/sortable task table across all organizations. |
| `/tasks/:id` | Task Detail | Full timeline (comments + run summaries), comment input, action buttons. |
| `/tasks/:id/runs/:runId` | Run Detail | Execution steps with tool calls, reasoning, final output. |
| `/chat` | Session List | All chat sessions with organization scope. |
| `/chat/:id` | Chat Interface | Full streaming chat with The Assistant. |

### 3.2 Navigation Layout

The application uses a **fixed left sidebar + main content area** layout.

```
┌──────────┬───────────────────────────────────────────┐
│          │  Breadcrumbs                               │
│  Logo    ├───────────────────────────────────────────┤
│          │                                           │
│ Dashboard│                                           │
│ Orgs     │         Main Content Area                 │
│ Tasks    │                                           │
│ Chat     │                                           │
│          │                                           │
│          │                                           │
│──────────│                                           │
│ Status   │                                           │
│ bar      │                                           │
└──────────┴───────────────────────────────────────────┘
```

**Sidebar contents (top to bottom):**
1. **Logo/wordmark**: "Sabbatical" text. Links to `/`.
2. **Navigation links**: Dashboard, Organizations, Tasks, Chat. Active link is visually highlighted.
3. **Status footer** (bottom of sidebar): Compact live indicator showing active workers count (e.g., "2/4 workers") and total system cost (e.g., "$12.47"). Updated via the same polling mechanism as the dashboard. This gives persistent cost/activity awareness from any page.

**Breadcrumbs**: Displayed at the top of the main content area, reflecting the current navigation path (e.g., `Organizations > react_app > frontend_dev`).

### 3.3 Responsive Behavior
- **Desktop (1024px+)**: Sidebar is permanently visible. Full layout as described above.
- **Tablet (768px–1023px)**: Sidebar collapses to icons only. Expands on hover or hamburger toggle. Main content fills the screen.
- **Below 768px**: Not a primary target. Sidebar becomes a slide-out drawer triggered by a hamburger icon.

---

## 4. Dashboard View

**Route**: `/`
**API**: `GET /api/status`, `GET /api/organizations`, `GET /api/tasks?status=in_progress`
**Polling**: Every 3 seconds.

### 4.1 Layout

The dashboard is a single-page overview with four sections:

**Section A: Server Status Bar**
A horizontal bar at the top displaying:
- Server status indicator (green dot + "Running").
- Active workers: `{active_workers} / {max_concurrency}` with a small progress bar.
- Total system cost: `${total_cost}` formatted to 2 decimal places.
- Total tokens: `{consumed_input_tokens + consumed_output_tokens}` formatted with `k` or `M` suffix.

**Section B: Task Status Cards**
Five cards in a horizontal row, one per status (`open`, `in_progress`, `failed`, `done`, `canceled`). Each card shows the count and a status-appropriate color/icon. The `failed` card uses a warning color (amber/red) when count > 0. Each card is clickable and navigates to `/tasks?status={status}`.

**Section C: Organization Summary Table**
A compact table listing all organizations (fetched from `GET /api/organizations`). Columns: Name, Agents, Cost. Each row links to `/organizations/:name`. Sorted by cost descending (most expensive first).

**Section D: Active Tasks Feed**
A live feed of in-progress tasks (fetched from `GET /api/tasks?status=in_progress`). Each entry shows: task ID, title, assignee (agent), organization, and elapsed time (computed from `current_run_elapsed_seconds`). Elapsed time updates every second via a client-side timer seeded from the API value. Each entry links to `/tasks/:id`.

### 4.2 Empty State
When no organizations exist, the dashboard shows a centered call-to-action: "No organizations yet. Create one to get started." with a button that opens the Create Organization dialog.

---

## 5. Organization Views

### 5.1 Organization List

**Route**: `/organizations`
**API**: `GET /api/organizations`
**Polling**: Every 5 seconds.

A table with columns:

| Column | Source |
|---|---|
| Name | `name` (link to detail) |
| Description | `description` (truncated to 80 chars) |
| Workspace | `workspace_path` (monospace, truncated with tooltip) |
| Agents | `agent_count` |
| Cost | `$total_cost` |

**Actions**:
- **"New Organization"** button (top-right) opens a creation dialog.
- Each row has a kebab menu (three dots) with: Edit, Delete.

### 5.2 Organization Detail

**Route**: `/organizations/:name`
**API**: `GET /api/organizations/:name` (returns agent hierarchy tree), `GET /api/tasks?organization=:name`
**Polling**: Every 5 seconds.

**Layout** (two-column on desktop):

**Left column (wider, ~60%): Agent Hierarchy Tree**
A visual tree rendering the `agents` array from the organization detail response. Each node shows:
- Agent name (link to agent detail).
- Description (if present, muted text below name).
- Model override badge (if non-null, e.g., a small pill showing the model name).
- Removed agents are excluded from this tree.

Tree lines use CSS borders (`border-left` + `border-bottom`) connecting parent to children, similar to a file tree in an IDE. Root agents appear at the top level. Subordinates are indented under their boss.

**Right column (~40%): Organization Info + Task Summary**
- **Info card**: Name, description, workspace path, total cost, total tokens.
- **Task status breakdown**: Five small status badges with counts (same as dashboard cards but scoped to this org). Each is clickable and navigates to `/tasks?organization=:name&status={status}`.
- **Recent tasks**: A compact list of the 5 most recent tasks in this organization, each linking to `/tasks/:id`.

**Actions**:
- **"Add Agent"** button above the hierarchy tree opens the agent creation form.
- **"Edit Organization"** button in the info card opens the edit dialog.
- **"Delete Organization"** button in the info card, guarded by a confirmation dialog. The dialog warns about cascade deletion and blocks if any task is `in_progress` (showing which tasks must be preempted first).

### 5.3 Create Organization Dialog

A modal dialog with fields:

| Field | Input Type | Validation |
|---|---|---|
| Name | Text input | Required, `snake_case` pattern enforced client-side. |
| Workspace Path | Text input | Required, must be an absolute path. |
| Description | Textarea | Optional. |

On submit, `POST /api/organizations`. On success, navigate to `/organizations/:name`. On error (409 duplicate, 422 validation), display inline error message below the relevant field.

### 5.4 Edit Organization Dialog

Pre-populated modal with workspace_path and description fields. Name is displayed but not editable. On submit, `PATCH /api/organizations/:name`.

---

## 6. Agent Views

### 6.1 Agent Detail

**Route**: `/organizations/:name/agents/:agentName`
**API**: `GET /api/organizations/:org/agents/:name`
**Polling**: Every 10 seconds (agent data changes infrequently).

**Header**: Agent name, organization (link back), boss (link to boss agent detail or "Root" badge), `is_removed` badge if applicable.

**Info Section**:
- Description.
- Instructions path (monospace).
- Max iterations.
- Model (or "System default" if null).
- Cost breakdown: input tokens, output tokens, total cost.

**Instructions Content**:
A collapsible panel (default expanded) rendering the full `instructions_content` field as Markdown. This gives immediate visibility into the agent's system prompt without leaving the browser.

**Subordinates**:
A list of direct subordinates (from the `subordinates` array), each linking to their agent detail page.

**Actions**:
- **"Edit Agent"** button opens the edit dialog.
- **"Remove Agent"** button opens a confirmation dialog. Blocked if agent has open/in-progress tasks (message explains which tasks). Warns about subordinate promotion to root.

### 6.2 Add Agent Dialog

Accessed from the Organization Detail page. A modal with fields:

| Field | Input Type | Validation |
|---|---|---|
| Name | Text input | Required, `snake_case`. |
| Description | Textarea | Optional. |
| Boss | Dropdown (populated from org agents) | Optional. Includes "(None — Root Agent)" option. |
| Instructions Path | Text input | Required. |
| Max Iterations | Number input | Optional (placeholder shows system default). |
| Model | Text input | Optional (placeholder shows "System default"). |

On submit, `POST /api/organizations/:org/agents`. On success, the organization detail view refreshes to show the new agent in the hierarchy.

### 6.3 Edit Agent Dialog

Pre-populated modal with same fields as Add Agent (except Name, which is read-only). Boss dropdown allows selecting any active agent in the org or "(None — Root Agent)". On submit, `PATCH /api/organizations/:org/agents/:name`.

---

## 7. Task Views

### 7.1 Task List

**Route**: `/tasks`
**API**: `GET /api/tasks` with query parameters.
**Polling**: Every 3 seconds.

**Filters** (displayed as a horizontal bar above the table):
- **Organization**: Dropdown populated from `GET /api/organizations` (includes "All" option).
- **Status**: Multi-select pills for `open`, `in_progress`, `failed`, `done`, `canceled`. All selected by default except `canceled`.
- **Assignee**: Text input with autocomplete (searches across agents in the selected organization, plus `user`).

Filters are reflected in URL query parameters (`/tasks?organization=react_app&status=open,in_progress`) so that links to filtered views are shareable and bookmarkable.

**Table columns**:

| Column | Source | Notes |
|---|---|---|
| ID | `id` | Link to task detail. Monospace. |
| Title | `title` | Truncated to 60 chars with tooltip. |
| Status | `status` | Color-coded badge (see Section 11). |
| Assignee | `assignee` | Link to agent detail if not "user". |
| Organization | `organization` | Link to org detail. |
| Cost | `$total_cost` | |
| Elapsed / Duration | `current_run_elapsed_seconds` or `total_duration_seconds` | For `in_progress` tasks, a live-updating timer. For completed tasks, total duration. |
| Created | `created_at` | Relative time (e.g., "2h ago") with absolute tooltip. |

Default sort: `in_progress` first, then `open`, then `failed`, then `done`, then `canceled`. Within each group, most recent first.

**Actions**:
- **"New Task"** button (top-right) opens the task creation dialog.

### 7.2 Task Detail

**Route**: `/tasks/:id`
**API**: `GET /api/tasks/:id` (returns full timeline).
**Polling**: Every 3 seconds when task is `open` or `in_progress`. Every 10 seconds for `done`, `failed`, `canceled`.

This is the **heart of the application**. The task detail view renders the task's timeline as a rich, conversation-like thread.

**Layout**:

```
┌────────────────────────────────────────────────────┐
│  REAC-0003  Implement dark mode toggle    [open]   │
│  Org: react_app    Assignee: frontend_dev          │
│  Cost: $0.32    Created: 2h ago                    │
│  ┌──────────────────────────────────────────────┐  │
│  │ Description                                   │  │
│  │ Add a dark mode toggle to the header...       │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ─── Action Bar ─────────────────────────────────  │
│  [Preempt] [Done] [Reopen] [Retry] [Cancel]       │
│                                                    │
│  ─── Timeline ───────────────────────────────────  │
│                                                    │
│  ┌ user · 2h ago ───────────────────────────────┐  │
│  │ @frontend_dev please implement dark mode      │  │
│  │ toggle in the header component.               │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌ RUN a1b2c3d4 · frontend_dev · 45s · $0.04 ──┐  │
│  │ ✓ success                  [View Details →]   │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌ frontend_dev · 1h ago ───────────────────────┐  │
│  │ I've added the toggle component in            │  │
│  │ `src/components/ThemeToggle.tsx`... @user      │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌ system · 1h ago ─────────────────────────────┐  │
│  │ [SYSTEM: No valid tag detected. Assigning     │  │
│  │  to user.]                                    │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ─── Comment Input ──────────────────────────────  │
│  ┌──────────────────────────────────────────────┐  │
│  │ Type a comment... @mention to assign          │  │
│  └──────────────────────────────────┤ Send ├────┘  │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Header**: Task ID (monospace), title, status badge, organization (link), assignee (link if agent), cost, created timestamp.

**Description**: Rendered as Markdown in a muted card below the header. Collapsed by default if longer than 5 lines, with a "Show more" toggle.

**Action Bar**: Contextual buttons based on current task state. Only valid actions are shown:

| Task Status | Assignee | Available Actions |
|---|---|---|
| `open` | `user` | Done, Cancel |
| `open` | agent | Cancel |
| `in_progress` | agent | Preempt, Cancel |
| `failed` | `user` | Reopen, Retry, Done, Cancel |
| `done` | `user` | Reopen |
| `canceled` | `user` | (none) |

The **Retry** button opens a small dropdown to select the target agent (defaulting to the last agent that ran).

**Timeline**: The core visual element. Each timeline entry is a card with distinct styling by type:

- **Comment (author=user)**: Left-aligned, blue-tinted border. Author label "you". Body rendered as Markdown.
- **Comment (author=agent)**: Left-aligned, green-tinted border. Author label is the agent name (link to agent detail). Body rendered as Markdown. `@` mentions are highlighted as colored pills within the text.
- **Comment (author=system)**: Full-width, muted gray background, smaller text. Italic. No border emphasis.
- **Run Summary**: Full-width, horizontal card with a distinct background (subtle gradient or dashed border). Shows: run ID (monospace, link to run detail), agent name, status badge, duration, cost. A "View Details" link navigates to the run detail page.

**Comment Input**: A textarea at the bottom of the timeline.
- **@-mention autocomplete**: When the user types `@`, a dropdown appears listing all active agents in the task's organization plus `user`. Navigable with arrow keys, selectable with Tab/Enter. The dropdown filters as the user types after `@`.
- The **Send** button submits via `POST /api/tasks/:id/comments`. Disabled while the request is in-flight.
- Disabled entirely when the task is `in_progress`, `done`, or `canceled`, with an explanatory tooltip (e.g., "Preempt the task before commenting").

### 7.3 Task Creation Dialog

A modal dialog with fields:

| Field | Input Type | Validation |
|---|---|---|
| Title | Text input | Required. |
| Organization | Dropdown (from `GET /api/organizations`) | Required. |
| Assignee | Dropdown (populated from agents in selected org + "user") | Defaults to "user". Updates when organization selection changes. |
| Description | Textarea (tall, supports Markdown) | Optional. Defaults to title if omitted by the API. |

On submit, `POST /api/tasks`. On success, navigate to `/tasks/:id`.

---

## 8. Run Views

### 8.1 Run List (Within Task Detail)

Runs are surfaced inline in the task timeline as run summary cards (Section 7.2). Additionally, the task detail view includes a collapsible **"All Runs"** section below the timeline that shows a compact table of all runs for the task (from `GET /api/tasks/:task_id/runs`).

| Column | Source |
|---|---|
| Run ID | `id` (link to detail, monospace) |
| Agent | `agent` |
| Model | `model_used` |
| Status | `status` badge |
| Duration | `duration_seconds` (formatted as `Xm Ys`) |
| Cost | `$total_cost` |
| Started | `started_at` (relative time) |

### 8.2 Run Detail

**Route**: `/tasks/:id/runs/:runId`
**API**: `GET /api/runs/:runId`
**Polling**: Every 3 seconds if run status is `running`. No polling for terminal statuses.

**Header**: Run ID, task ID (link back to task), agent (link), organization, status badge, model used, duration, cost, token breakdown (input/output).

**Execution Steps**: The primary content. Each step in the `execution_steps` array is rendered as a distinct, vertically-stacked block:

**Step Type: `llm_reasoning`**
- Rendered as a card with a "thought bubble" icon (brain/lightbulb).
- Background: faint purple/blue tint.
- Content rendered as Markdown.
- Collapsible if longer than 10 lines. Default: collapsed for all but the first and last reasoning steps.

**Step Type: `tool_call`**
- Rendered as a card with a "wrench/terminal" icon.
- Background: faint amber/yellow tint.
- **Tool name** displayed as a badge (e.g., `file_write`, `shell`).
- **Arguments** displayed in a collapsible code block (JSON-formatted). Default: collapsed.
- **Output** displayed in a collapsible code block with syntax highlighting. Default: collapsed. Outputs longer than 500 characters show the first 500 with a "Show full output" toggle.

**Step Type: `final_output`**
- Rendered as a prominent card with a "check/flag" icon.
- Background: faint green tint, stronger border.
- Content rendered as Markdown. `@` mentions highlighted as pills.
- Always expanded. Never collapsed.

**Step Number**: Each step displays its ordinal number (`Step 1`, `Step 2`, ...) in a left-margin gutter, connected by a vertical line (like a Git commit graph) to provide visual sequencing.

---

## 9. Chat / Session Views

### 9.1 Session List

**Route**: `/chat`
**API**: `GET /api/sessions`
**Polling**: Every 10 seconds.

A list of session cards (not a table), displayed as a vertical stack. Each card shows:
- Title (or "Untitled" if null).
- Organization scope badge (or "Global").
- Cost.
- Created timestamp (relative).

Clicking a card navigates to `/chat/:id`.

**Actions**:
- **"New Chat"** button opens a small dialog to optionally select an organization scope, then creates a session via `POST /api/sessions` and navigates to `/chat/:id`.

### 9.2 Chat Interface

**Route**: `/chat/:id`
**API**: `GET /api/sessions/:id` (initial load), `POST /api/sessions/:id/messages` (send, SSE stream).

The chat interface is a full-height, single-column view optimized for conversation.

**Layout**:

```
┌──────────────────────────────────────────────────┐
│  Chat: Bootstrap frontend org  │  Org: react_app │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌─ you ────────────────────────────────────┐    │
│  │ I need an organization to build a React   │    │
│  │ frontend with a Node backend.             │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ┌─ assistant ──────────────────────────────┐    │
│  │ Here's a proposed organizational          │    │
│  │ structure...                               │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ┌─ assistant (streaming...) ───────────────┐    │
│  │ Let me think about the best...█           │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
├──────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────┤ Send ├─┐│
│ │ Type a message...                              ││
│ └────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────┘
```

**Header bar**: Session title (or "New Chat"), organization scope badge, cost for this session.

**Message area**: Scrollable conversation history. Auto-scrolls to bottom on new messages. Messages are rendered as Markdown.
- **User messages**: Left-aligned with "you" label, distinct background.
- **Assistant messages**: Left-aligned with "assistant" label, distinct background.

**Streaming behavior**:
1. User types message and clicks Send (or presses Enter for single-line, Shift+Enter for newline).
2. Input is disabled. A new assistant message bubble appears with a blinking cursor.
3. The client uses `fetch()` with `ReadableStream` to consume the SSE response from the `POST` endpoint. (The native `EventSource` API only supports GET, so `fetch` is required here.)
4. Each `token` event appends content to the streaming message bubble.
5. On the `done` event, the final message replaces the streamed content (ensuring consistency), cost in the header updates, and the input is re-enabled.
6. On network error, the streaming message is replaced with an error indicator and the input is re-enabled.

**Input area**: A resizable textarea. Send button is disabled while streaming or when input is empty.

---

## 10. Real-Time Updates — Polling Strategy

The web app uses **polling via TanStack Query's `refetchInterval`** for all live data. There is no WebSocket connection.

### 10.1 Polling Intervals

| View / Data | Interval | Rationale |
|---|---|---|
| Dashboard status (`GET /api/status`) | 3s | Core system health must feel live. |
| Dashboard org table (`GET /api/organizations`) | 3s | Cost accumulation is continuous. |
| Dashboard active tasks (`GET /api/tasks?status=in_progress`) | 3s | Active work changes rapidly. |
| Task list | 3s | Status transitions happen frequently during active work. |
| Task detail (open / in_progress) | 3s | Timeline grows during active execution. |
| Task detail (done / failed / canceled) | 10s | Rarely changes; mostly for detecting reopens. |
| Organization list | 5s | Moderate change frequency. |
| Organization detail | 5s | Agent additions are infrequent. |
| Agent detail | 10s | Agent profiles rarely change. |
| Run detail (running) | 3s | Steps accumulate during execution. |
| Run detail (terminal) | None | Terminal runs never change. |
| Session list | 10s | Low urgency. |
| Sidebar status footer | 3s | Shares the dashboard status query (same cache key). |

### 10.2 Polling Behavior
- **Tab visibility**: Polling is paused when the browser tab is not visible. TanStack Query's `refetchOnWindowFocus` handles revalidation on return.
- **Stale-while-revalidate**: The UI always shows the last known data while a fresh fetch is in-flight. No loading spinners on refetch — only on initial load.
- **Query deduplication**: Multiple components requesting the same data (e.g., sidebar footer and dashboard both reading `/api/status`) share a single query and single network request.

### 10.3 Elapsed Time Timers
For `in_progress` tasks, the `current_run_elapsed_seconds` value from the API seeds a client-side `setInterval` that increments every second. This avoids polling the API every second just for a timer. The timer resyncs on each API poll.

---

## 11. UI Components — Reusable Building Blocks

### 11.1 Status Badge
A pill-shaped badge with color and icon per status:

| Status | Color | Icon |
|---|---|---|
| `open` | Blue | Circle outline |
| `in_progress` | Amber/Yellow | Spinning loader |
| `failed` | Red | X circle |
| `done` | Green | Check circle |
| `canceled` | Gray | Slash circle |

Used for both task status and run status. Run statuses use the same color mapping: `running` = amber, `success` = green, `failed` = red, `preempted` = gray.

### 11.2 Cost Display
Formats cost values consistently: `$0.00` for zero, `$0.04` for small values, `$12.47` for larger values. Always 2 decimal places. Monospace font for alignment in tables.

### 11.3 Token Display
Formats token counts with magnitude suffix: `482k` for thousands, `1.2M` for millions. Tooltip shows exact count.

### 11.4 Relative Timestamp
Displays "2m ago", "3h ago", "yesterday", etc. Tooltip shows the exact ISO timestamp. Updates every minute via a shared timer (not per-component interval).

### 11.5 Agent Hierarchy Tree
A recursive component rendering the nested agent array from `GET /api/organizations/:name`. Uses CSS indentation with connector lines. Each node is interactive (clickable to navigate to agent detail).

### 11.6 Markdown Renderer
Used for: task descriptions, comment bodies, agent instructions, assistant messages. Renders standard Markdown plus GFM tables and code blocks (with syntax highlighting via `shiki`). `@mentions` within rendered text are detected via regex and rendered as colored inline pills.

### 11.7 @-Mention Autocomplete
A dropdown triggered by typing `@` in the comment input. Fetches the agent list for the task's organization. Filters as the user types. Inserts the selected name into the textarea. Keyboard-navigable (arrow keys + Enter).

### 11.8 Confirmation Dialog
A modal with a warning message and two buttons: "Cancel" and a destructive action button (red). Used for: Delete Organization, Remove Agent, Cancel Task. Includes specific context about what will be affected (e.g., "This will permanently delete organization 'react_app' and all 3 agents, 12 tasks, and 4 chat sessions.").

### 11.9 Empty State
A centered illustration/icon with explanatory text and a primary action button. Used when: no organizations exist, no tasks match filters, no chat sessions exist.

---

## 12. Interactions & Microinteractions

### 12.1 Loading States
- **Initial page load**: Skeleton placeholders (gray animated bars) in the shape of the expected content. No blank screens.
- **Polling refetch**: No loading indicator. Stale data remains visible. A subtle "refreshing" dot animation in the page header is optional.
- **Action in-flight** (e.g., creating a task): Button shows a spinner and is disabled. Form inputs are disabled.

### 12.2 Optimistic Updates
- **Comment submission**: The comment appears immediately in the timeline (with a subtle "sending" indicator) before the API responds. On error, the comment is removed and an error toast is shown.
- **Task actions** (done, cancel, preempt, reopen): The status badge updates immediately. On error, it reverts.

### 12.3 Error Handling
- **API errors (4xx)**: Displayed as inline messages near the relevant form field or as toast notifications for actions.
- **Network errors**: A persistent banner at the top of the page: "Unable to reach the Sabbatical server. Is it running?" with a retry button. Appears after 3 consecutive failed polls.
- **409 Conflict errors**: Displayed with specific guidance (e.g., "Cannot delete organization: task REAC-0003 is in progress. Preempt it first.").

### 12.4 Transitions
- **Page navigation**: Instant (no page-level transition animations). Content fades in subtly (150ms opacity transition).
- **Expandable sections** (run steps, descriptions): Smooth height transition (200ms ease).
- **Modal dialogs**: Fade + scale entrance (150ms), fade exit (100ms). Backdrop blur.
- **Toast notifications**: Slide in from top-right, auto-dismiss after 5 seconds, manually dismissable.

### 12.5 Keyboard Shortcuts
- `/` — Focus the search/filter input on the current page (if applicable).
- `n` — Open the "New" dialog for the current context (New Task on tasks page, New Chat on chat page).
- `Esc` — Close any open modal/dialog.

---

## 13. Serving Strategy

### 13.1 Production: Bundled Static Files

The web app is built into static files (`index.html`, JS bundles, CSS) and served directly by the FastAPI server. This is the production/installed mode.

**Build output location**: `src/sabbatical/web/dist/`

**Server integration**: The FastAPI `create_app()` function mounts the built web app after all `/api` routers are registered:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# After all /api routers are registered:
web_dist = Path(__file__).parent.parent / "web" / "dist"
if web_dist.exists():
    app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="web-assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # Serve index.html for all non-API, non-asset routes (SPA client-side routing)
        return FileResponse(web_dist / "index.html")
```

This means:
- The API is available at `http://localhost:7420/api/...` (unchanged).
- The web app is available at `http://localhost:7420/` and all non-`/api` routes.
- Client-side routing works because all unmatched paths serve `index.html`.
- No additional process, port, or configuration is needed.

**Build step**: The web app is built as part of the package build process. The `web/` directory at the project root contains the source. A build script (`npm run build` in `web/`) outputs to `src/sabbatical/web/dist/`. This directory is included in the Python package distribution.

### 13.2 Development: Vite Dev Server + API Proxy

During development, the Vite dev server runs separately (e.g., on port 5173) with a proxy configuration that forwards `/api` requests to the running Sabbatical API server:

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:7420',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../src/sabbatical/web/dist',
    emptyOutDir: true,
  },
});
```

This provides hot module replacement during frontend development while using the real API backend.

### 13.3 CORS

In production (static files served by FastAPI), CORS is not needed (same origin). In development, the Vite proxy handles the cross-origin issue transparently. No CORS middleware is required on the FastAPI server for web app support.

### 13.4 Web App Source Location

```
web/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── index.html
├── public/
│   └── favicon.svg
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/
    │   ├── client.ts               # Fetch wrapper (base URL, error handling)
    │   ├── types.ts                 # TypeScript types mirroring API response models
    │   ├── queries.ts               # TanStack Query hooks (useStatus, useTasks, etc.)
    │   └── mutations.ts             # TanStack Query mutation hooks
    ├── components/
    │   ├── layout/
    │   │   ├── Sidebar.tsx
    │   │   ├── Breadcrumbs.tsx
    │   │   └── AppLayout.tsx
    │   ├── shared/
    │   │   ├── StatusBadge.tsx
    │   │   ├── CostDisplay.tsx
    │   │   ├── TokenDisplay.tsx
    │   │   ├── RelativeTime.tsx
    │   │   ├── MarkdownRenderer.tsx
    │   │   ├── ConfirmDialog.tsx
    │   │   ├── EmptyState.tsx
    │   │   └── Toast.tsx
    │   ├── organizations/
    │   │   ├── OrgList.tsx
    │   │   ├── OrgDetail.tsx
    │   │   ├── OrgForm.tsx
    │   │   └── AgentTree.tsx
    │   ├── agents/
    │   │   ├── AgentDetail.tsx
    │   │   └── AgentForm.tsx
    │   ├── tasks/
    │   │   ├── TaskList.tsx
    │   │   ├── TaskDetail.tsx
    │   │   ├── TaskForm.tsx
    │   │   ├── TaskTimeline.tsx
    │   │   ├── TimelineComment.tsx
    │   │   ├── TimelineRunSummary.tsx
    │   │   ├── CommentInput.tsx
    │   │   ├── MentionAutocomplete.tsx
    │   │   └── TaskActions.tsx
    │   ├── runs/
    │   │   ├── RunDetail.tsx
    │   │   ├── RunStepReasoning.tsx
    │   │   ├── RunStepToolCall.tsx
    │   │   └── RunStepFinalOutput.tsx
    │   └── chat/
    │       ├── SessionList.tsx
    │       ├── ChatInterface.tsx
    │       ├── ChatMessage.tsx
    │       └── ChatInput.tsx
    ├── pages/
    │   ├── DashboardPage.tsx
    │   ├── OrganizationsPage.tsx
    │   ├── OrganizationDetailPage.tsx
    │   ├── AgentDetailPage.tsx
    │   ├── TasksPage.tsx
    │   ├── TaskDetailPage.tsx
    │   ├── RunDetailPage.tsx
    │   ├── ChatListPage.tsx
    │   └── ChatPage.tsx
    └── lib/
        ├── format.ts                # Cost, token, time formatting utilities
        ├── constants.ts             # Polling intervals, color mappings
        └── hooks.ts                 # Shared custom hooks (useElapsedTimer, etc.)
```

---

## 14. Edge Cases & Constraints

### 14.1 Server Unavailable
When the API server is not running, the web app shows a full-page "Server Offline" state with instructions to run `sabbatical server up`. All polling stops. A background health check (`GET /api/status`) runs every 5 seconds and automatically transitions to the dashboard when the server comes online.

### 14.2 Stale Data After Action
After any mutation (create, update, delete, task action), the relevant TanStack Query caches are invalidated to trigger an immediate refetch. For example, after `POST /api/tasks/:id/done`, both the task detail query and the task list query are invalidated.

### 14.3 Concurrent CLI + Web Usage
Since both clients are stateless REST consumers, there are no conflicts. The polling mechanism ensures the web app picks up changes made via the CLI within the polling interval (worst case: 3 seconds for actively-polled views).

### 14.4 Long Task Timelines
For tasks with many comments and runs (50+ timeline entries), the timeline uses virtualized (windowed) rendering to maintain scroll performance. Only visible entries are rendered in the DOM.

### 14.5 Large Execution Steps
Run execution steps with very long tool outputs (e.g., large file writes, verbose shell output) are truncated by default (500 characters) with an explicit "Show full output" toggle, matching the CLI's `--full` behavior.

### 14.6 SSE Reconnection
If the SSE stream for a chat message is interrupted (network hiccup), the UI shows the partial message received so far with an error indicator and a "Retry" button. The retry re-sends the original message to `POST /api/sessions/:id/messages`.

### 14.7 Color Scheme
The web app defaults to a **dark color scheme** (dark backgrounds, light text). This aligns with the developer-centric audience and reduces visual fatigue during monitoring. A light mode toggle is a future consideration but not in scope for V1.
