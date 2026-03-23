# Context Management & Prompt Caching

## 1. Philosophy & Caching Architecture
To ensure scalable and cost-effective orchestration, the context payload injected into every worker thread is strictly ordered to maximize LLM prompt caching (leveraging OpenRouter's supported caching mechanisms). Because caching systems rely on a contiguous, immutable prefix, the payload is divided into a "Static Prefix" (frozen across the organization) and a "Dynamic Suffix" (the evolving task state). Any text mutation busts the cache for all subsequent tokens, meaning all dynamic data must reside at the absolute bottom of the prompt payload.

---

## 2. Block A: System Rules & Protocol (Static Prefix)
The foundational rules of the Sabbatical engine. This section establishes context (how Sabbatical works, how the comment thread functions) before introducing operational rules. It is structured around these sections:

* **How Sabbatical Works:** Frames the comment thread as the team's shared living record. Establishes that the agent has no memory outside the thread — reading it carefully is how the agent understands the history of the work.
* **Private Work, Public Voice:** Clearly separates private execution (tool calls, internal reasoning — invisible to others) from the public final message (appended verbatim to the thread as a permanent comment, the only artifact anyone else will ever see).
* **The Comment Thread:** Reinforces that the final message is a contribution to a collaborative record. Because the next agent cannot see tool calls or reasoning, the message must contain everything relevant for work to continue.
* **Handoff Protocol:** The final message controls routing via `@` tags. The Dispatcher parses tags **only from the agent's final output message** (after all tool use completes) and routes based on the first valid tag found (the "First Valid Tag" rule). Invalid tags are skipped. If no valid tag remains, the system escalates to the agent's Boss; if the agent is a root agent (no Boss), the task defaults to the user. Self-tagging is allowed but discouraged.
* **Iteration Budget & Error Handling:** Operational constraints on turn limits and how to handle blockers (document clearly, escalate rather than silently fail).

---

## 3. Block B: Organization Topology (Static Prefix)
Contextualizes the agent within the broader project and organizational environment, enabling intelligent collaboration.

* **Organization Purpose:** The overarching goal or project context extracted from the organization creation metadata (the `--description` field).
* **The Roster (Tree-Based):** The full agent roster is injected as an indented tree reflecting the organizational hierarchy (e.g., YAML or plain text representation), rather than a flat list. This provides spatial awareness so the agent understands its place in the hierarchy, who its manager is, and who its direct reports are. The exact literal string names must be included to ensure the Dispatcher's "First Tag" routing rule does not fail due to a misspelled tag.
* **Peer Descriptions:** Each agent's `description` field (a brief one-liner of role and expertise) is displayed alongside its name in the roster tree, so the active agent knows who to route work to next.

This tree-based formatting explicitly trains the stateless profile on its place in the world, allowing it to make intelligent delegation decisions without bloated, repetitive instructions in its core identity prompt.

---

## 4. Block C: Agent Profile & Capabilities (Static Prefix)
The agent's identity, presented as a character to inhabit rather than configuration to follow. Structured in two sections:

* **Identity First (`## You Are: {name}`):** The agent's name followed immediately by the raw `.md` file referenced by the agent's `instructions_path`, containing the agent's core persona, domain expertise, and working style. Instructions come before any operational context so the agent reads who it is and steps into that role before seeing hierarchy or constraints.
* **Place in the Organization:** Declaration of the agent's Boss (if any) and Direct Reports. The hierarchy is presented as informational — the Boss is the default escalation path, direct reports are natural delegates, but the agent may tag any agent in the roster. If Boss is null, the agent is a hierarchy root.
* **Iteration Budget:** The agent's `max_iterations` limit, placed at the end of the block as operational context rather than a configuration field.

---

## 5. Block D: Task State & Comments (Dynamic Suffix)
The cache-busting section. This is the only part of the payload that mutates between worker thread executions. It is placed at the very end of the prompt (as the user message, not the system prompt) to protect the caching of Blocks A–C. Presented as a "Task Briefing" — a briefing the agent receives before acting.

* **Task Header:** `id` and `title` presented as a bold header (like a ticket title), with `organization` as metadata.
* **What Needs to Be Done:** The detailed spec/description of the task (the `description` field), framed actively rather than as a passive "Description" label.
* **Thread — Team History on This Task:** The chronological transcript of `comments` only. This includes prior agent final outputs (which serve as summaries of what was accomplished during each Run, e.g., files modified, code snippets changed), `@tags`, system notes, and human interventions. **Run execution details (tool calls, internal reasoning, raw stdout/stderr) are not included** — they are stored in separate Run records and are not part of the agent context payload. When the thread is empty, the message reads "(This task has just been opened. You are the first to work on it.)" to orient the agent.
* **Closing Instruction:** Invites the agent to act and write their message to the team, reinforcing that the message becomes the next comment in the thread and should include an @tag for routing.

*(Note on MVP Scope: Context bloat within the comment thread is intentionally ignored for V1. The priority is establishing the correct caching architecture; thread summarization will be handled in a future iteration.)*
