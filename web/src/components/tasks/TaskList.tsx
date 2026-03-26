import { useState, useMemo } from "react";
import { Link, useSearchParams } from "react-router";
import { Search, X } from "lucide-react";
import { useTasks } from "@/api/queries";
import { useCurrentOrg } from "@/context/OrgContext";
import { useOrgLinks } from "@/lib/orgLinks";
import type { TaskStatus } from "@/api/types";
import StatusBadge from "@/components/shared/StatusBadge";
import CostDisplay from "@/components/shared/CostDisplay";
import RelativeTime from "@/components/shared/RelativeTime";
import PageSkeleton from "@/components/shared/PageSkeleton";
import { formatDuration } from "@/lib/format";
import { STATUS_ORDER } from "@/lib/constants";
import { useElapsedTimer } from "@/lib/hooks";

const ALL_STATUSES: TaskStatus[] = [
  "open",
  "in_progress",
  "failed",
  "done",
  "canceled",
];

const QUICK_FILTERS = [
  { label: "Active", statuses: ["open", "in_progress", "failed"] },
  { label: "Done", statuses: ["done"] },
  { label: "All", statuses: [] },
] as const;

function TaskElapsed({
  seconds,
  isActive,
}: {
  seconds: number | null;
  isActive: boolean;
}) {
  const elapsed = useElapsedTimer(seconds, isActive);
  return (
    <span className="font-mono text-xs">
      {elapsed !== null ? formatDuration(elapsed) : "-"}
    </span>
  );
}

export default function TaskList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { orgName } = useCurrentOrg();
  const links = useOrgLinks();
  const [search, setSearch] = useState("");

  const statusFilter = searchParams.get("status") ?? "";
  const activeStatuses = statusFilter
    ? statusFilter.split(",")
    : ["open", "in_progress", "failed", "done"];

  const { data: tasks, isLoading } = useTasks({
    organization: orgName,
    status: statusFilter || undefined,
  });

  const toggleStatus = (s: TaskStatus) => {
    const current = new Set(activeStatuses);
    if (current.has(s)) current.delete(s);
    else current.add(s);
    const newParams = new URLSearchParams(searchParams);
    if (current.size === 0 || current.size === ALL_STATUSES.length) {
      newParams.delete("status");
    } else {
      newParams.set("status", [...current].join(","));
    }
    setSearchParams(newParams);
  };

  const applyQuickFilter = (statuses: readonly string[]) => {
    const newParams = new URLSearchParams(searchParams);
    if (statuses.length === 0) {
      newParams.delete("status");
    } else {
      newParams.set("status", statuses.join(","));
    }
    setSearchParams(newParams);
  };

  const sortedTasks = useMemo(() => {
    let result = tasks?.slice() ?? [];

    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (t) =>
          t.title.toLowerCase().includes(q) ||
          t.id.toLowerCase().includes(q) ||
          t.assignee.toLowerCase().includes(q),
      );
    }

    return result.sort((a, b) => {
      const orderDiff = STATUS_ORDER[a.status] - STATUS_ORDER[b.status];
      if (orderDiff !== 0) return orderDiff;
      return (
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    });
  }, [tasks, search]);

  if (isLoading) return <PageSkeleton variant="list" />;

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search tasks..."
            className="h-9 w-48 rounded-md border border-border-default bg-surface-raised pl-8 pr-8 text-sm text-text-primary placeholder:text-text-muted focus:border-primary-500 focus:outline-none sm:w-64"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-text-muted hover:text-text-secondary"
            >
              <X size={14} />
            </button>
          )}
        </div>

        <div className="flex rounded-md border border-border-default">
          {QUICK_FILTERS.map((qf) => {
            const isActive =
              qf.statuses.length === 0
                ? !statusFilter
                : statusFilter === qf.statuses.join(",");
            return (
              <button
                key={qf.label}
                onClick={() => applyQuickFilter(qf.statuses)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors first:rounded-l-md last:rounded-r-md ${
                  isActive
                    ? "bg-surface-overlay text-text-primary"
                    : "text-text-muted hover:text-text-secondary hover:bg-surface-raised"
                }`}
              >
                {qf.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Status pills */}
      <div className="flex gap-1.5">
        {ALL_STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => toggleStatus(s)}
            className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
              activeStatuses.includes(s)
                ? "bg-surface-overlay text-text-primary"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            <StatusBadge status={s} size="sm" />
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-border-default">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-default bg-surface text-left text-xs text-text-muted">
              <th className="px-4 py-2.5 font-medium">ID</th>
              <th className="px-4 py-2.5 font-medium">Title</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Assignee</th>
              <th className="px-4 py-2.5 font-medium text-right">Cost</th>
              <th className="px-4 py-2.5 font-medium text-right">Duration</th>
              <th className="px-4 py-2.5 font-medium text-right">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {sortedTasks.map((task) => (
              <tr
                key={task.id}
                className="group transition-colors hover:bg-surface-raised/50"
              >
                <td className="px-4 py-2.5">
                  <Link
                    to={links.task(task.id)}
                    className="font-mono text-xs text-primary-400 hover:text-primary-300"
                  >
                    {task.id}
                  </Link>
                </td>
                <td className="px-4 py-2.5 max-w-xs">
                  <Link
                    to={links.task(task.id)}
                    className="text-text-primary hover:text-primary-400 truncate block transition-colors"
                  >
                    {task.title}
                  </Link>
                </td>
                <td className="px-4 py-2.5">
                  <StatusBadge status={task.status} size="sm" />
                </td>
                <td className="px-4 py-2.5 text-text-secondary">
                  {task.assignee === "user" ? (
                    "user"
                  ) : (
                    <Link
                      to={links.agent(task.assignee)}
                      className="hover:text-primary-400 transition-colors"
                    >
                      {task.assignee}
                    </Link>
                  )}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <CostDisplay value={task.total_cost} className="text-xs" />
                </td>
                <td className="px-4 py-2.5 text-right text-text-secondary">
                  {task.status === "in_progress" ? (
                    <TaskElapsed
                      seconds={task.current_run_elapsed_seconds}
                      isActive
                    />
                  ) : (
                    <span className="font-mono text-xs">
                      {formatDuration(task.total_duration_seconds)}
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <RelativeTime
                    datetime={task.created_at}
                    className="text-xs"
                  />
                </td>
              </tr>
            ))}
            {sortedTasks.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-text-muted"
                >
                  {search
                    ? `No tasks matching "${search}"`
                    : "No tasks match the current filters"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
