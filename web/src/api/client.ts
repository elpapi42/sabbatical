import type {
  ApiError,
  StatusResponse,
  OrganizationCreate,
  OrganizationUpdate,
  OrganizationSummary,
  OrganizationDetail,
  AgentCreate,
  AgentUpdate,
  AgentSummary,
  AgentDetail,
  TaskCreate,
  TaskDetail,
  TaskSummary,
  TaskActionResult,
  CommentCreate,
  CommentResult,
  RunSummary,
  RunDetail,
  SessionCreate,
  SessionSummary,
  SessionDetail,
  MessageCreate,
  TaskListParams,
} from "./types";

const API_BASE = "/api";

class ApiRequestError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const err: ApiError = await res.json();
      detail = err.detail || detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiRequestError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// Status
export const getStatus = () => apiFetch<StatusResponse>("/status");

// Organizations
export const getOrganizations = () =>
  apiFetch<{ organizations: OrganizationSummary[] }>("/organizations").then(
    (r) => r.organizations,
  );

export const getOrganization = (name: string) =>
  apiFetch<OrganizationDetail>(`/organizations/${name}`);

export const createOrganization = (data: OrganizationCreate) =>
  apiFetch<OrganizationDetail>("/organizations", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateOrganization = (name: string, data: OrganizationUpdate) =>
  apiFetch<OrganizationDetail>(`/organizations/${name}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const deleteOrganization = (name: string) =>
  apiFetch<void>(`/organizations/${name}`, { method: "DELETE" });

// Agents
export const getAgents = (org: string, includeRemoved = false) =>
  apiFetch<{ agents: AgentSummary[] }>(
    `/organizations/${org}/agents${includeRemoved ? "?include_removed=true" : ""}`,
  ).then((r) => r.agents);

export const getAgent = (org: string, name: string) =>
  apiFetch<AgentDetail>(`/organizations/${org}/agents/${name}`);

export const createAgent = (org: string, data: AgentCreate) =>
  apiFetch<AgentDetail>(`/organizations/${org}/agents`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateAgent = (org: string, name: string, data: AgentUpdate) =>
  apiFetch<AgentDetail>(`/organizations/${org}/agents/${name}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const deleteAgent = (org: string, name: string) =>
  apiFetch<{ removed: string; warnings: string[] }>(
    `/organizations/${org}/agents/${name}`,
    { method: "DELETE" },
  );

// Tasks
export const getTasks = (params?: TaskListParams) => {
  const searchParams = new URLSearchParams();
  if (params?.organization) searchParams.set("organization", params.organization);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.assignee) searchParams.set("assignee", params.assignee);
  const qs = searchParams.toString();
  return apiFetch<{ tasks: TaskSummary[] }>(`/tasks${qs ? `?${qs}` : ""}`).then(
    (r) => r.tasks,
  );
};

export const getTask = (id: string) => apiFetch<TaskDetail>(`/tasks/${id}`);

export const createTask = (data: TaskCreate) =>
  apiFetch<TaskDetail>("/tasks", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const commentTask = (id: string, data: CommentCreate) =>
  apiFetch<CommentResult>(`/tasks/${id}/comments`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const preemptTask = (id: string) =>
  apiFetch<TaskActionResult>(`/tasks/${id}/preempt`, { method: "POST" });

export const doneTask = (id: string) =>
  apiFetch<TaskActionResult>(`/tasks/${id}/done`, { method: "POST" });

export const reopenTask = (id: string) =>
  apiFetch<TaskActionResult>(`/tasks/${id}/reopen`, { method: "POST" });

export const retryTask = (id: string, assignee?: string) => {
  const qs = assignee ? `?assignee=${encodeURIComponent(assignee)}` : "";
  return apiFetch<TaskActionResult>(`/tasks/${id}/retry${qs}`, {
    method: "POST",
  });
};

export const cancelTask = (id: string) =>
  apiFetch<TaskActionResult>(`/tasks/${id}/cancel`, { method: "POST" });

// Runs
export const getTaskRuns = (taskId: string) =>
  apiFetch<{ runs: RunSummary[] }>(`/tasks/${taskId}/runs`).then((r) => r.runs);

export const getRun = (id: string) => apiFetch<RunDetail>(`/runs/${id}`);

// Sessions
export const getSessions = (orgScope?: string) => {
  const qs = orgScope
    ? `?organization_scope=${encodeURIComponent(orgScope)}`
    : "";
  return apiFetch<{ sessions: SessionSummary[] }>(`/sessions${qs}`).then(
    (r) => r.sessions,
  );
};

export const getSession = (id: string) =>
  apiFetch<SessionDetail>(`/sessions/${id}`);

export const createSession = (data: SessionCreate) =>
  apiFetch<SessionDetail>("/sessions", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const sendMessage = (
  sessionId: string,
  data: MessageCreate,
): Promise<Response> =>
  fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

export { ApiRequestError };
