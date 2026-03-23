# Implementation: Assistant

## 14. The Assistant

### `assistant/runtime.py`

The Assistant is a separate ADK Agent with its own tools for state manipulation. It runs within the API Server and streams responses via SSE.

```python
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.lite_llm import LiteLlm
from sabbatical.assistant.tools import create_assistant_tools

def create_assistant_agent(config, db, organization_scope=None):
    llm = LiteLlm(
        model=f"openrouter/{config.llm.assistant_model}",
        api_key=config.llm.openrouter_api_key,
    )

    tools = create_assistant_tools(db, organization_scope)

    instruction = ASSISTANT_SYSTEM_PROMPT  # Constant: planning copilot identity,
                                           # strict non-execution rules, proposal/approval flow

    if organization_scope:
        instruction += f"\n\nYou are scoped to organization: {organization_scope}"

    agent = Agent(
        name="assistant",
        model=llm,
        instruction=instruction,
        tools=tools,
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="sabbatical_assistant",
        agent=agent,
        session_service=session_service,
    )

    return runner
```

### `assistant/tools.py`

The Assistant's tools are thin wrappers around the same database operations the API endpoints use. They allow the Assistant to create organizations, add agents, create tasks, etc. — but only after proposing and receiving user approval in the conversation.

```python
def create_assistant_tools(db, organization_scope=None):

    async def create_organization(name: str, workspace_path: str,
                                  description: str = "") -> str:
        """Create a new organization. Use this after the user approves your proposal."""
        # Same validation + DB insert as the API endpoint
        ...

    async def write_instructions_file(name: str, organization: str, content: str) -> str:
        """Generate the .md instructions artifact for an agent.
        Writes to <workspace_path>/.sabbatical/agents/<name>.md
        Returns the absolute path to the generated file."""
        # Resolves org workspace_path, ensures dir exists, writes file
        ...

    async def add_agent(name: str, organization: str, instructions_path: str,
                        description: str = "", boss: str = "", max_iterations: int = 50) -> str:
        """Add an agent to an organization. Use this after the user approves."""
        ...

    async def create_task(title: str, organization: str,
                          description: str = "", assignee: str = "user") -> str:
        """Create a task. Use this after the user approves."""
        ...

    async def list_agents(organization: str) -> str:
        """List all agents in an organization."""
        ...

    async def list_tasks(organization: str) -> str:
        """List all tasks in an organization."""
        ...

    tools = [create_organization, write_instructions_file, add_agent, create_task, list_agents, list_tasks]

    return tools
```

### SSE Streaming Endpoint

```python
# server/routers/sessions.py (streaming portion)

from sse_starlette.sse import EventSourceResponse
from google.adk.agents.run_config import RunConfig, StreamingMode

@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: MessageCreate, ...):
    session = await fetch_session(db, session_id)
    runner = create_assistant_agent(config, db, session["organization_scope"])

    # Persist user message
    await save_message(db, session_id, "user", body.content)

    # Auto-generate title on first message
    if not session["title"]:
        new_title = body.content[:47] + "..." if len(body.content) > 50 else body.content
        await update_session_title(db, session_id, new_title)

    # Reconstruct conversation history for the LLM (required for session resume)
    prior_messages = await fetch_session_messages(db, session_id)
    for msg in prior_messages[:-1]:  # Exclude the message we just saved
        await runner.session_service.append_event(
            session_id=session_id,
            event=types.Content(role=msg["role"], parts=[types.Part(text=msg["content"])]),
        )

    async def event_generator():
        full_text = ""
        total_input = 0
        total_output = 0

        async for event in runner.run_async(
            user_id="sabbatical",
            session_id=session_id,
            new_message=types.Content(
                role="user", parts=[types.Part(text=body.content)]
            ),
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            if event.partial and event.content:
                chunk = event.content.parts[0].text if event.content.parts else ""
                yield {"event": "token", "data": json.dumps({"content": chunk})}
                full_text += chunk

            if event.usage_metadata and not event.partial:
                total_input += event.usage_metadata.prompt_token_count or 0
                total_output += event.usage_metadata.candidates_token_count or 0

            if not event.partial and event.content:
                full_text = "".join(
                    p.text for p in event.content.parts if p.text
                )

        # Persist assistant message and update session costs
        await save_message(db, session_id, "assistant", full_text)
        await update_session_costs(db, session_id, total_input, total_output)

        yield {
            "event": "done",
            "data": json.dumps({
                "message": {
                    "role": "assistant",
                    "content": full_text,
                    "created_at": utc_now(),
                },
                "usage": {
                    "consumed_input_tokens": total_input,
                    "consumed_output_tokens": total_output,
                    "total_cost": 0.0,
                },
            }),
        }

    return EventSourceResponse(event_generator())
```

---

