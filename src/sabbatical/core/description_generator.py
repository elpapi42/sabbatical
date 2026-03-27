import logging
import uuid
from pathlib import Path

from google.adk import Agent, Runner
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.genai import types

from sabbatical.core.config import SabbaticalConfig

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a technical writer. You will be given an agent's instructions file. Your job is to produce a detailed description of the agent's role, expertise, and responsibilities, then call the set_description tool with it. Do not include any other text or explanation."""

USER_PROMPT = """Here are the agent instructions:

---
{instructions}
---

Call set_description with a detailed description (4-6 sentences) covering the agent's role, key expertise areas, and primary responsibilities."""


async def generate_description(
    instructions_path: str, config: SabbaticalConfig
) -> str | None:
    try:
        content = Path(instructions_path).read_text()
    except Exception:
        logger.warning(
            "Could not read instructions at %s, skipping description generation",
            instructions_path,
        )
        return None

    result = {"description": None}

    def set_description(description: str) -> str:
        """Set the agent's detailed role description (2-4 sentences).

        Args:
            description: A detailed description of the agent's role, expertise, and responsibilities.
        """
        result["description"] = description
        return "Description set."

    try:
        llm = LiteLlm(
            model=f"openrouter/{config.llm.default_model}",
            api_key=config.llm.openrouter_api_key,
        )

        agent = Agent(
            name="description_writer",
            model=llm,
            instruction=SYSTEM_PROMPT,
            tools=[set_description],
        )

        session_service = InMemorySessionService()
        runner = Runner(
            app_name="sabbatical_desc",
            agent=agent,
            session_service=session_service,
            auto_create_session=True,
        )

        session_id = f"desc-{uuid.uuid4().hex[:8]}"
        user_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=USER_PROMPT.format(instructions=content))],
        )

        async for event in runner.run_async(
            session_id=session_id,
            user_id="system",
            new_message=user_message,
        ):
            pass  # just drive the agent to completion

        if result["description"]:
            logger.info(
                "Generated description for %s: %s",
                instructions_path,
                result["description"],
            )
        else:
            logger.warning(
                "Agent did not call set_description for %s", instructions_path
            )

        return result["description"]
    except Exception:
        logger.warning(
            "Failed to generate description for %s",
            instructions_path,
            exc_info=True,
        )
        return None
