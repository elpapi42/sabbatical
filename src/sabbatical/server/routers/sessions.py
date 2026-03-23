import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.genai import types
from sse_starlette.sse import EventSourceResponse

from sabbatical.assistant.runtime import create_assistant_agent
from sabbatical.models import (
    MessageCreate,
    SessionCreate,
    SessionDetail,
    SessionMessage,
    SessionSummary,
)
from sabbatical.server.dependencies import get_config, get_db

router = APIRouter(tags=["Sessions"])


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(session: SessionCreate, db=Depends(get_db)):
    sid = f"CHAT-{uuid.uuid4().hex[:6]}"
    now = utc_now()
    if session.organization_scope:
        org = await db.fetch_one(
            "SELECT name FROM organizations WHERE name = :org",
            {"org": session.organization_scope},
        )
        if not org:
            return JSONResponse(
                status_code=404,
                content={
                    "message": f"Organization '{session.organization_scope}' not found."
                },
            )

    await db.execute(
        "INSERT INTO sessions (id, organization_scope, created_at) VALUES (:id, :org, :now)",
        {"id": sid, "org": session.organization_scope, "now": now},
    )
    return {
        "id": sid,
        "organization_scope": session.organization_scope,
        "title": None,
        "consumed_input_tokens": 0,
        "consumed_output_tokens": 0,
        "total_cost": 0.0,
        "created_at": now,
    }


@router.get("/sessions")
async def list_sessions(organization_scope: Optional[str] = None, db=Depends(get_db)):
    query = "SELECT * FROM sessions"
    values = {}
    if organization_scope:
        query += " WHERE organization_scope = :org"
        values["org"] = organization_scope

    rows = await db.fetch_all(query, values)
    sessions = [
        SessionSummary(
            id=r["id"],
            organization_scope=r["organization_scope"],
            title=r["title"],
            total_cost=r["total_cost"],
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
        ).model_dump()
        for r in rows
    ]
    return {"sessions": sessions}


@router.get("/sessions/{id}")
async def get_session(id: str, db=Depends(get_db)):
    s = await db.fetch_one("SELECT * FROM sessions WHERE id = :id", {"id": id})
    if not s:
        return JSONResponse(
            status_code=404, content={"message": f"Session '{id}' not found."}
        )

    msgs = await db.fetch_all(
        "SELECT * FROM session_messages WHERE session_id = :id ORDER BY created_at ASC",
        {"id": id},
    )
    messages = [
        SessionMessage(
            role=m["role"],
            content=m["content"] or "",
            created_at=datetime.fromisoformat(m["created_at"].replace("Z", "+00:00")),
        )
        for m in msgs
    ]

    return SessionDetail(
        id=s["id"],
        organization_scope=s["organization_scope"],
        title=s["title"],
        total_cost=s["total_cost"],
        created_at=datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")),
        consumed_input_tokens=s["consumed_input_tokens"],
        consumed_output_tokens=s["consumed_output_tokens"],
        messages=messages,
    ).model_dump()


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str, body: MessageCreate, db=Depends(get_db), config=Depends(get_config)
):
    db_session = await db.fetch_one(
        "SELECT * FROM sessions WHERE id = :id", {"id": session_id}
    )
    if not db_session:
        return JSONResponse(
            status_code=404, content={"message": f"Session '{session_id}' not found."}
        )

    now = utc_now()
    await db.execute(
        "INSERT INTO session_messages (session_id, role, content, created_at) VALUES (:sid, 'user', :content, :now)",
        {"sid": session_id, "content": body.content, "now": now},
    )

    if not db_session["title"]:
        content_text = body.content if body.content else ""
        new_title = (
            (content_text[:47] + "...") if len(content_text) > 50 else content_text
        )
        await db.execute(
            "UPDATE sessions SET title = :title WHERE id = :id",
            {"title": new_title, "id": session_id},
        )

    runner = create_assistant_agent(config, db, db_session["organization_scope"])

    # Initialize the ADK session and capture the returned session object
    adk_session = await runner.session_service.create_session(
        app_name="sabbatical_assistant", user_id="sabbatical", session_id=session_id
    )

    prior_messages = await db.fetch_all(
        "SELECT * FROM session_messages WHERE session_id = :id ORDER BY created_at ASC",
        {"id": session_id},
    )

    for msg in prior_messages[:-1]:
        content_text = msg["content"] if msg["content"] else ""
        event = Event(
            author="sabbatical",
            content=types.Content(
                role=msg["role"],
                parts=[types.Part.from_text(text=content_text)],
            ),
        )
        await runner.session_service.append_event(session=adk_session, event=event)

    async def event_generator():
        full_text = ""
        total_input = 0
        total_output = 0

        async for event in runner.run_async(
            user_id="sabbatical",
            session_id=session_id,
            new_message=types.Content(
                role="user", parts=[types.Part.from_text(text=body.content)]
            ),
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            if event.partial and event.content and event.content.parts:
                first_part = event.content.parts[0]
                chunk = first_part.text if first_part and first_part.text else ""
                if chunk:
                    yield {"event": "token", "data": json.dumps({"content": chunk})}
                    full_text += chunk

            if event.usage_metadata and not event.partial:
                total_input += event.usage_metadata.prompt_token_count or 0
                total_output += event.usage_metadata.candidates_token_count or 0

            if not event.partial and event.content and event.content.parts:
                full_text = "".join(p.text or "" for p in event.content.parts if p.text)

        end_now = utc_now()
        await db.execute(
            "INSERT INTO session_messages (session_id, role, content, created_at) VALUES (:sid, 'assistant', :content, :now)",
            {"sid": session_id, "content": full_text, "now": end_now},
        )
        await db.execute(
            "UPDATE sessions SET consumed_input_tokens = consumed_input_tokens + :in_tok, consumed_output_tokens = consumed_output_tokens + :out_tok WHERE id = :id",
            {"in_tok": total_input, "out_tok": total_output, "id": session_id},
        )

        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "content": full_text,
                        "created_at": end_now,
                    },
                    "usage": {
                        "consumed_input_tokens": total_input,
                        "consumed_output_tokens": total_output,
                        "total_cost": 0.0,
                    },
                }
            ),
        }

    return EventSourceResponse(event_generator())
