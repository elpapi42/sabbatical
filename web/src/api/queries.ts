import { useQuery } from "@tanstack/react-query";
import {
  getStatus,
  getOrganizations,
  getOrganization,
  getAgents,
  getAgent,
  getTasks,
  getTask,
  getTaskRuns,
  getRun,
} from "./client";
import type { TaskListParams } from "./types";
import { POLL_FAST, POLL_MEDIUM, POLL_SLOW } from "@/lib/constants";

export function useStatus() {
  return useQuery({
    queryKey: ["status"],
    queryFn: getStatus,
    refetchInterval: POLL_FAST,
  });
}

export function useOrganizations() {
  return useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
    refetchInterval: POLL_MEDIUM,
  });
}

export function useOrganization(name: string) {
  return useQuery({
    queryKey: ["organizations", name],
    queryFn: () => getOrganization(name),
    refetchInterval: POLL_MEDIUM,
    enabled: !!name,
  });
}

export function useAgents(org: string, includeRemoved = false) {
  return useQuery({
    queryKey: ["agents", org, { includeRemoved }],
    queryFn: () => getAgents(org, includeRemoved),
    refetchInterval: POLL_SLOW,
    enabled: !!org,
  });
}

export function useAgent(org: string, name: string) {
  return useQuery({
    queryKey: ["agents", org, name],
    queryFn: () => getAgent(org, name),
    refetchInterval: POLL_SLOW,
    enabled: !!org && !!name,
  });
}

export function useTasks(params?: TaskListParams) {
  return useQuery({
    queryKey: ["tasks", params],
    queryFn: () => getTasks(params),
    refetchInterval: POLL_FAST,
  });
}

export function useTask(id: string) {
  return useQuery({
    queryKey: ["tasks", id],
    queryFn: () => getTask(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "open" || status === "in_progress") return POLL_FAST;
      return POLL_SLOW;
    },
    enabled: !!id,
  });
}

export function useTaskRuns(taskId: string) {
  return useQuery({
    queryKey: ["tasks", taskId, "runs"],
    queryFn: () => getTaskRuns(taskId),
    enabled: !!taskId,
  });
}

export function useRun(id: string) {
  return useQuery({
    queryKey: ["runs", id],
    queryFn: () => getRun(id),
    refetchInterval: (query) => {
      if (query.state.data?.status === "running") return POLL_FAST;
      return false;
    },
    enabled: !!id,
  });
}

