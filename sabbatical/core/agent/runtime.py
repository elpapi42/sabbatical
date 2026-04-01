import logging
import uuid

from google.adk import Agent, Runner
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService

from sabbatical.core.agent.tools import create_thread_tools, create_workspace_tools

logger = logging.getLogger(__name__)


def create_agent_runner(
    agent_name: str,
    system_prompt: str,
    model: str,
    openrouter_api_key: str,
    workspace_path: str,
    max_iterations: int,
    valid_route_targets: set[str] | None = None,
) -> tuple[Runner, str, dict]:
    logger.debug(
        "creating agent runner agent=%s model=%s workspace=%s",
        agent_name,
        model,
        workspace_path,
    )

    llm = LiteLlm(
        model=f"openrouter/{model}",
        api_key=openrouter_api_key,
    )

    thread_state = {
        "pending_comments": [],
        "comment_count": 0,
    }

    workspace_tools = create_workspace_tools(workspace_path)
    thread_tools = create_thread_tools(thread_state)
    tools = workspace_tools + thread_tools

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
        auto_create_session=True,
    )

    session_id = f"run-{uuid.uuid4().hex[:8]}"

    return runner, session_id, thread_state
