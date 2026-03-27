// Status types
export type TaskStatus =
  | "open"
  | "in_progress"
  | "failed"
  | "done"
  | "canceled";
export type RunStatus = "running" | "success" | "failed" | "preempted";
export type StepType = "llm_reasoning" | "tool_call" | "final_output" | "fatal_error";

// API error
export interface ApiError {
  detail: string;
}

// Status
export interface StatusResponse {
  server: string;
  tasks: Record<TaskStatus, number>;
  active_workers: number;
  max_concurrency: number;
  consumed_input_tokens: number;
  consumed_output_tokens: number;
  total_cost: number;
}

// Organizations
export interface OrganizationCreate {
  name: string;
  workspace_path: string;
  description?: string;
}

export interface OrganizationUpdate {
  workspace_path?: string;
  description?: string;
}

export interface OrganizationSummary {
  name: string;
  description: string | null;
  workspace_path: string;
  agent_count: number;
  consumed_input_tokens: number;
  consumed_output_tokens: number;
  total_cost: number;
}

export interface AgentNode {
  name: string;
  description: string | null;
  instructions_path: string;
  max_iterations: number;
  model: string | null;
  is_removed: boolean;
  subordinates: AgentNode[];
}

export interface OrganizationDetail {
  name: string;
  description: string | null;
  workspace_path: string;
  consumed_input_tokens: number;
  consumed_output_tokens: number;
  total_cost: number;
  agents: AgentNode[];
}

// Agents
export interface AgentCreate {
  name: string;
  description?: string;
  boss?: string;
  instructions_path: string;
  max_iterations?: number;
  model?: string;
}

export interface AgentUpdate {
  description?: string;
  boss?: string | null;
  instructions_path?: string;
  max_iterations?: number;
  model?: string;
}

export interface AgentSummary {
  name: string;
  organization: string;
  description: string | null;
  boss: string | null;
  instructions_path: string;
  max_iterations: number;
  model: string | null;
  is_removed: boolean;
  consumed_input_tokens: number;
  consumed_output_tokens: number;
  total_cost: number;
}

export interface AgentDetail extends AgentSummary {
  instructions_content: string;
  subordinates: AgentNode[];
}

// Tasks
export interface TaskCreate {
  title: string;
  organization: string;
  description?: string;
}

export interface CommentCreate {
  body: string;
}

export interface TimelineComment {
  type: "comment";
  author: string;
  body: string;
  created_at: string;
}

export interface TimelineRunSummary {
  type: "run_summary";
  run_id: string;
  agent: string;
  status: RunStatus;
  duration_seconds: number | null;
  cost: number;
  started_at: string;
  ended_at: string | null;
}

export type TimelineEntry = TimelineComment | TimelineRunSummary;

export interface TaskSummary {
  id: string;
  title: string;
  status: TaskStatus;
  organization: string;
  assignee: string;
  consumed_input_tokens: number;
  consumed_output_tokens: number;
  total_cost: number;
  created_at: string;
  current_run_elapsed_seconds: number | null;
  total_duration_seconds: number | null;
}

export interface TaskDetail {
  id: string;
  organization: string;
  title: string;
  description: string;
  status: TaskStatus;
  assignee: string;
  consumed_input_tokens: number;
  consumed_output_tokens: number;
  total_cost: number;
  created_at: string;
  timeline: TimelineEntry[];
}

export interface TaskActionResult {
  id: string;
  status: TaskStatus;
  assignee: string;
  preempted_run: string | null;
}

export interface CommentResult {
  comment: TimelineComment;
  task: TaskActionResult;
}

// Runs
export interface RunSummary {
  id: string;
  task_id: string;
  agent: string;
  organization: string;
  status: RunStatus;
  duration_seconds: number | null;
  total_cost: number;
  model_used: string | null;
  started_at: string;
  ended_at: string | null;
}

export interface ExecutionStep {
  step: number;
  type: StepType;
  content: string | null;
  tool: string | null;
  arguments: Record<string, unknown> | null;
  output: string | null;
}

export interface RunDetail extends RunSummary {
  consumed_input_tokens: number;
  consumed_output_tokens: number;
  execution_steps: ExecutionStep[];
}

// Sessions
export interface SessionCreate {
  organization_scope?: string;
}

export interface SessionSummary {
  id: string;
  organization_scope: string | null;
  title: string | null;
  total_cost: number;
  created_at: string;
}

export interface SessionMessage {
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface SessionDetail extends SessionSummary {
  consumed_input_tokens: number;
  consumed_output_tokens: number;
  messages: SessionMessage[];
}

export interface MessageCreate {
  content: string;
}

// Query params
export interface TaskListParams {
  organization?: string;
  status?: string;
  assignee?: string;
}
