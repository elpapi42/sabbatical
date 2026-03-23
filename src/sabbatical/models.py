from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_snake_case(v: str) -> str:
    if v in ("user", "system"):
        raise ValueError("Name is reserved")
    if not SNAKE_CASE_RE.match(v):
        raise ValueError(
            "Must be snake_case (lowercase, underscores, starts with letter)"
        )
    return v


# ── Organizations ──


class OrganizationCreate(BaseModel):
    name: str
    workspace_path: str
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return validate_snake_case(v)


class OrganizationUpdate(BaseModel):
    workspace_path: Optional[str] = None
    description: Optional[str] = None


class OrganizationSummary(BaseModel):
    name: str
    description: Optional[str]
    workspace_path: str
    agent_count: int
    consumed_input_tokens: int
    consumed_output_tokens: int
    total_cost: float


class AgentNode(BaseModel):
    name: str
    description: Optional[str]
    instructions_path: str
    max_iterations: int
    model: Optional[str]
    is_removed: bool
    subordinates: list[AgentNode] = []


class OrganizationDetail(BaseModel):
    name: str
    description: Optional[str]
    workspace_path: str
    consumed_input_tokens: int
    consumed_output_tokens: int
    total_cost: float
    agents: list[AgentNode]


# ── Agents ──


class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    boss: Optional[str] = None
    instructions_path: str
    max_iterations: Optional[int] = None
    model: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return validate_snake_case(v)


class AgentUpdate(BaseModel):
    description: Optional[str] = None
    boss: Optional[str] = None  # null means promote to root
    instructions_path: Optional[str] = None
    max_iterations: Optional[int] = None
    model: Optional[str] = None


class AgentSummary(BaseModel):
    name: str
    organization: str
    description: Optional[str]
    boss: Optional[str]
    instructions_path: str
    max_iterations: int
    model: Optional[str]
    is_removed: bool
    consumed_input_tokens: int
    consumed_output_tokens: int
    total_cost: float


class AgentDetail(AgentSummary):
    instructions_content: str
    subordinates: list[AgentNode]


# ── Tasks ──


class TaskCreate(BaseModel):
    title: str
    organization: str
    assignee: Optional[str] = "user"
    description: Optional[str] = None


class TaskSummary(BaseModel):
    id: str
    title: str
    status: str
    organization: str
    assignee: str
    consumed_input_tokens: int
    consumed_output_tokens: int
    total_cost: float
    created_at: datetime
    current_run_elapsed_seconds: Optional[float] = None


class TimelineComment(BaseModel):
    type: Literal["comment"] = "comment"
    author: str
    body: str
    created_at: datetime


class TimelineRunSummary(BaseModel):
    type: Literal["run_summary"] = "run_summary"
    run_id: str
    agent: str
    status: str
    duration_seconds: Optional[float]
    cost: float
    started_at: datetime
    ended_at: Optional[datetime]


class TaskDetail(BaseModel):
    id: str
    organization: str
    title: str
    description: str
    status: str
    assignee: str
    consumed_input_tokens: int
    consumed_output_tokens: int
    total_cost: float
    created_at: datetime
    timeline: list[TimelineComment | TimelineRunSummary]


class CommentCreate(BaseModel):
    body: str


class TaskActionResult(BaseModel):
    id: str
    status: str
    assignee: str
    preempted_run: Optional[str] = None


class CommentResult(BaseModel):
    comment: TimelineComment
    task: TaskActionResult


# ── Runs ──


class RunSummary(BaseModel):
    id: str
    task_id: str
    agent: str
    organization: str
    status: str
    duration_seconds: Optional[float]
    total_cost: float
    started_at: datetime
    ended_at: Optional[datetime]


class ExecutionStep(BaseModel):
    step: int
    type: str  # "llm_reasoning", "tool_call", "final_output"
    content: Optional[str] = None
    tool: Optional[str] = None
    arguments: Optional[dict] = None
    output: Optional[str] = None


class RunDetail(RunSummary):
    model_used: Optional[str]
    consumed_input_tokens: int
    consumed_output_tokens: int
    execution_steps: list[ExecutionStep]


# ── Sessions ──


class SessionCreate(BaseModel):
    organization_scope: Optional[str] = None


class SessionSummary(BaseModel):
    id: str
    organization_scope: Optional[str]
    title: Optional[str]
    total_cost: float
    created_at: datetime


class SessionMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class SessionDetail(SessionSummary):
    consumed_input_tokens: int
    consumed_output_tokens: int
    messages: list[SessionMessage]


class MessageCreate(BaseModel):
    content: str
