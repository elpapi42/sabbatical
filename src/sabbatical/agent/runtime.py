import uuid

from google.adk import Agent, Runner
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.genai import types

from sabbatical.agent.tools import create_workspace_tools


def create_agent_runner(
    agent_name: str,
    system_prompt: str,
    model: str,
    openrouter_api_key: str,
    workspace_path: str,
    max_iterations: int,
) -> tuple[Runner, str]:
    llm = LiteLlm(
        model=f"openrouter/{model}",
        api_key=openrouter_api_key,
    )

    tools = create_workspace_tools(workspace_path)

    agent = Agent(
        name=agent_name,
        model=llm,
        instruction=system_prompt,
        tools=tools,
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="sabbatical",
        agent=agent,
        session_service=session_service,
    )

    session_id = f"run-{uuid.uuid4().hex[:8]}"

    return runner, session_id
