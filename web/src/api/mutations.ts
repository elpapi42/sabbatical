import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createOrganization,
  updateOrganization,
  deleteOrganization,
  createAgent,
  updateAgent,
  deleteAgent,
  createTask,
  commentTask,
  preemptTask,
  doneTask,
  reopenTask,
  retryTask,
  cancelTask,
  createSession,
} from "./client";
import type {
  OrganizationCreate,
  OrganizationUpdate,
  AgentCreate,
  AgentUpdate,
  TaskCreate,
  CommentCreate,
  SessionCreate,
} from "./types";

// Organizations
export function useCreateOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrganizationCreate) => createOrganization(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["organizations"] }),
  });
}

export function useUpdateOrganization(name: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrganizationUpdate) => updateOrganization(name, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organizations"] });
      qc.invalidateQueries({ queryKey: ["organizations", name] });
    },
  });
}

export function useDeleteOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => deleteOrganization(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["organizations"] }),
  });
}

// Agents
export function useCreateAgent(org: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AgentCreate) => createAgent(org, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents", org] });
      qc.invalidateQueries({ queryKey: ["organizations", org] });
    },
  });
}

export function useUpdateAgent(org: string, name: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AgentUpdate) => updateAgent(org, name, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents", org] });
      qc.invalidateQueries({ queryKey: ["agents", org, name] });
    },
  });
}

export function useDeleteAgent(org: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => deleteAgent(org, name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents", org] });
      qc.invalidateQueries({ queryKey: ["organizations", org] });
    },
  });
}

// Tasks
export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: TaskCreate) => createTask(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

export function useCommentTask(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CommentCreate) => commentTask(taskId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks", taskId] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}

export function usePreemptTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => preemptTask(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["tasks", id] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["status"] });
    },
  });
}

export function useDoneTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => doneTask(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["tasks", id] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["status"] });
    },
  });
}

export function useReopenTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => reopenTask(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["tasks", id] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["status"] });
    },
  });
}

export function useRetryTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, assignee }: { id: string; assignee?: string }) =>
      retryTask(id, assignee),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["tasks", id] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["status"] });
    },
  });
}

export function useCancelTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cancelTask(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["tasks", id] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["status"] });
    },
  });
}

// Sessions
export function useCreateSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: SessionCreate) => createSession(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
}
