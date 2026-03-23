# Context Management & Prompt Caching

## 1. Philosophy & Caching Architecture
To ensure scalable and cost-effective orchestration, the context payload injected into every worker thread is strictly ordered to maximize LLM prompt caching (leveraging OpenRouter's supported caching mechanisms). Because caching systems rely on a contiguous, immutable prefix, the payload is divided into a "Static Prefix" (frozen across the organization) and a "Dynamic Suffix" (the evolving task state). Any text mutation busts the cache for all subsequent tokens, meaning all dynamic data must reside at the absolute bottom of the prompt payload.

---

## 2. Block A: System Rules & Protocol (Static Prefix)
The foundational rules of the Sabbatical engine. This section teaches the stateless model how to operate within the local dispatcher environment.

* **The Handoff Protocol:** Instructions explaining how agents collaborate via `@` tags within the same organization. The Dispatcher parses tags **only from the agent's final output message** (after all tool use completes). If the agent includes one or more valid `@agent_name` or `@user` tags, the Dispatcher routes based on the first valid tag found (the "First Tag" rule). Both `@agent_name` and `@user` are valid under this rule. Self-tagging is allowed but not promoted. If the agent produces output with no valid tag, the Dispatcher escalates to the agent's Boss; if the agent is a root agent (no Boss), the task defaults to the user.
* **Execution Constraints:** Rules enforcing that the agent operates asynchronously and must rely on provided tools to interact with the local machine within the Organization's `workspace_path`.
* **Formatting Rules:** Expected output formats (e.g., separating internal reasoning from the final output comment).

---

## 3. Block B: Organization Topology (Static Prefix)
Contextualizes the agent within the broader project and organizational environment, enabling intelligent collaboration.

* **Organization Purpose:** The overarching goal or project context extracted from the organization creation metadata (the `--description` field).
* **The Roster (Tree-Based):** The full agent roster is injected as an indented tree reflecting the organizational hierarchy (e.g., YAML or plain text representation), rather than a flat list. This provides spatial awareness so the agent understands its place in the hierarchy, who its manager is, and who its direct reports are. The exact literal string names must be included to ensure the Dispatcher's "First Tag" routing rule does not fail due to a misspelled tag.
* **Peer Descriptions:** Each agent's `description` field (a brief one-liner of role and expertise) is displayed alongside its name in the roster tree, so the active agent knows who to route work to next.

This tree-based formatting explicitly trains the stateless profile on its place in the world, allowing it to make intelligent delegation decisions without bloated, repetitive instructions in its core identity prompt.

---

## 4. Block C: Agent Profile & Capabilities (Static Prefix)
The specific identity and operational boundaries of the active worker.

* **The Identity:** The raw `.md` file referenced by the agent's `instructions_path`, containing the agent's core system prompt, persona, and domain expertise.
* **Chain of Command:** Declaration of the agent's Boss (if any) and Subordinates. If Boss is null, the agent is a hierarchy root. The hierarchy is informational to guide delegation decisions but is not enforced by the Dispatcher.
* **Operational Limits:** The agent's `max_iterations` limit, informing the model of its iteration budget.

---

## 5. Block D: Task State & Comments (Dynamic Suffix)
The cache-busting section. This is the only part of the payload that mutates between worker thread executions. It is placed at the very end of the prompt to protect the caching of Blocks A–C.

* **Task Metadata:** `id`, `organization`, and `title`.
* **Task Description:** The detailed spec/description of the task (the `description` field).
* **The Comment Thread:** The chronological transcript of `comments` only. This includes prior agent final outputs (which serve as summaries of what was accomplished during each Run, e.g., files modified, code snippets changed), `@tags`, system notes, and human interventions. **Run execution details (tool calls, internal reasoning, raw stdout/stderr) are not included** — they are stored in separate Run records and are not part of the agent context payload. This keeps the context lean and cost-effective.

*(Note on MVP Scope: Context bloat within the comment thread is intentionally ignored for V1. The priority is establishing the correct caching architecture; thread summarization will be handled in a future iteration.)*
