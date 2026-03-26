import { Link } from "react-router";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useTask, useTaskRuns } from "@/api/queries";
import { useOrgLinks } from "@/lib/orgLinks";
import StatusBadge from "@/components/shared/StatusBadge";
import CostDisplay from "@/components/shared/CostDisplay";
import RelativeTime from "@/components/shared/RelativeTime";
import MarkdownRenderer from "@/components/shared/MarkdownRenderer";
import PageSkeleton from "@/components/shared/PageSkeleton";
import TaskTimeline from "./TaskTimeline";
import TaskActions from "./TaskActions";
import CommentInput from "./CommentInput";
import { formatDuration } from "@/lib/format";

interface Props {
  taskId: string;
}

export default function TaskDetail({ taskId }: Props) {
  const { data: task, isLoading } = useTask(taskId);
  const { data: runs } = useTaskRuns(taskId);
  const links = useOrgLinks();
  const [descExpanded, setDescExpanded] = useState(false);
  const [runsExpanded, setRunsExpanded] = useState(false);

  if (isLoading || !task) return <PageSkeleton variant="detail" />;

  const commentDisabled =
    task.status === "in_progress" ||
    task.status === "done" ||
    task.status === "canceled";

  const disabledReason =
    task.status === "in_progress"
      ? "Preempt the task before commenting"
      : task.status === "done"
        ? "Reopen the task to comment"
        : task.status === "canceled"
          ? "Canceled tasks cannot receive comments"
          : undefined;

  const descriptionLines = task.description?.split("\n").length ?? 0;
  const descriptionLong = descriptionLines > 5;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-text-primary">{task.title}</h1>
          <StatusBadge status={task.status} size="md" />
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-muted">
          <span className="font-mono text-xs">{task.id}</span>
          <span className="text-border-default">·</span>
          <span>
            Assignee:{" "}
            {task.assignee === "user" ? (
              "user"
            ) : (
              <Link
                to={links.agent(task.assignee)}
                className="text-primary-400 hover:text-primary-300"
              >
                {task.assignee}
              </Link>
            )}
          </span>
          <span className="text-border-default">·</span>
          <CostDisplay value={task.total_cost} className="text-sm" />
          <span className="text-border-default">·</span>
          <RelativeTime datetime={task.created_at} className="text-sm" />
        </div>
      </div>

      {/* Description */}
      {task.description && (
        <div className="rounded-lg border border-border-default">
          <button
            onClick={() => setDescExpanded(!descExpanded)}
            className="flex w-full items-center justify-between px-4 py-2.5 text-xs font-semibold text-text-muted uppercase tracking-wider hover:bg-surface-raised/50 transition-colors"
          >
            Description
            {descriptionLong &&
              (descExpanded ? (
                <ChevronDown size={14} />
              ) : (
                <ChevronRight size={14} />
              ))}
          </button>
          <div
            className={`border-t border-border-default px-4 py-3 ${
              !descExpanded && descriptionLong
                ? "max-h-32 overflow-hidden relative after:absolute after:bottom-0 after:left-0 after:right-0 after:h-8 after:bg-gradient-to-t after:from-neutral-950"
                : ""
            }`}
          >
            <MarkdownRenderer content={task.description} />
          </div>
        </div>
      )}

      {/* Action Bar */}
      <TaskActions task={task} />

      {/* Timeline */}
      <div>
        <h2 className="mb-3 text-xs font-semibold text-text-muted uppercase tracking-wider">
          Timeline
        </h2>
        <TaskTimeline
          timeline={task.timeline}
          taskId={task.id}
          organization={task.organization}
        />
      </div>

      {/* Comment Input */}
      <CommentInput
        taskId={task.id}
        organization={task.organization}
        disabled={commentDisabled}
        disabledReason={disabledReason}
      />

      {/* All Runs */}
      {runs && runs.length > 0 && (
        <div className="rounded-lg border border-border-default">
          <button
            onClick={() => setRunsExpanded(!runsExpanded)}
            className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-text-primary hover:bg-surface-raised/50 transition-colors"
          >
            <span>All Runs ({runs.length})</span>
            {runsExpanded ? (
              <ChevronDown size={16} />
            ) : (
              <ChevronRight size={16} />
            )}
          </button>
          {runsExpanded && (
            <div className="border-t border-border-default">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-text-muted">
                    <th className="px-4 py-2 font-medium">Run ID</th>
                    <th className="px-4 py-2 font-medium">Agent</th>
                    <th className="px-4 py-2 font-medium">Model</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium text-right">Duration</th>
                    <th className="px-4 py-2 font-medium text-right">Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {runs.map((run) => (
                    <tr
                      key={run.id}
                      className="transition-colors hover:bg-surface-raised/50"
                    >
                      <td className="px-4 py-2">
                        <Link
                          to={links.run(taskId, run.id)}
                          className="font-mono text-xs text-primary-400 hover:text-primary-300"
                        >
                          {run.id}
                        </Link>
                      </td>
                      <td className="px-4 py-2 text-text-secondary">{run.agent}</td>
                      <td className="px-4 py-2 text-xs text-text-muted">
                        {run.model_used ?? "-"}
                      </td>
                      <td className="px-4 py-2">
                        <StatusBadge status={run.status} size="sm" />
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-xs text-text-secondary">
                        {formatDuration(run.duration_seconds)}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <CostDisplay value={run.total_cost} className="text-xs" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
