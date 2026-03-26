import { useState } from "react";
import { Link } from "react-router";
import {
  Loader2,
  Circle,
  XCircle,
  CheckCircle2,
  Ban,
  Plus,
  Pencil,
  Trash2,
  Zap,
  DollarSign,
  Hash,
  ChevronDown,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";
import { useCurrentOrg } from "@/context/OrgContext";
import { useOrgLinks } from "@/lib/orgLinks";
import { useTasks, useStatus } from "@/api/queries";
import { useDeleteOrganization } from "@/api/mutations";
import type { TaskStatus } from "@/api/types";
import { formatCost, formatTokens, formatDuration } from "@/lib/format";
import { useElapsedTimer } from "@/lib/hooks";
import BreadcrumbBar from "@/components/layout/BreadcrumbBar";
import MarkdownRenderer from "@/components/shared/MarkdownRenderer";
import PageSkeleton from "@/components/shared/PageSkeleton";
import CostDisplay from "@/components/shared/CostDisplay";
import StatusBadge from "@/components/shared/StatusBadge";
import AgentTree from "@/components/organizations/AgentTree";
import AgentForm from "@/components/agents/AgentForm";
import OrgForm from "@/components/organizations/OrgForm";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { useToast } from "@/components/shared/Toast";
import { useNavigate } from "react-router";

const statusConfig: Record<
  TaskStatus,
  { label: string; icon: LucideIcon; color: string; bg: string }
> = {
  open: {
    label: "Open",
    icon: Circle,
    color: "text-blue-400",
    bg: "bg-blue-500/10 border-blue-500/20",
  },
  in_progress: {
    label: "In Progress",
    icon: Loader2,
    color: "text-amber-400",
    bg: "bg-amber-500/10 border-amber-500/20",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    color: "text-red-400",
    bg: "bg-red-500/10 border-red-500/20",
  },
  done: {
    label: "Done",
    icon: CheckCircle2,
    color: "text-green-400",
    bg: "bg-green-500/10 border-green-500/20",
  },
  canceled: {
    label: "Canceled",
    icon: Ban,
    color: "text-neutral-400",
    bg: "bg-neutral-500/10 border-neutral-500/20",
  },
};

function MetricCard({
  icon: Icon,
  label,
  value,
  subtext,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  subtext?: string;
}) {
  return (
    <div className="rounded-lg border border-border-default bg-surface-raised p-4">
      <div className="flex items-center gap-2 text-text-muted">
        <Icon size={14} />
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div className="mt-2 text-xl font-bold text-text-primary font-mono">
        {value}
      </div>
      {subtext && (
        <div className="mt-0.5 text-xs text-text-muted">{subtext}</div>
      )}
    </div>
  );
}

function ActiveTaskRow({
  task,
}: {
  task: {
    id: string;
    title: string;
    assignee: string;
    current_run_elapsed_seconds: number | null;
  };
}) {
  const links = useOrgLinks();
  const elapsed = useElapsedTimer(
    task.current_run_elapsed_seconds,
    task.current_run_elapsed_seconds !== null,
  );

  return (
    <Link
      to={links.task(task.id)}
      className="flex items-center justify-between px-4 py-2.5 text-sm transition-colors hover:bg-surface-raised/50"
    >
      <div className="flex items-center gap-3 min-w-0">
        <Loader2 size={14} className="shrink-0 animate-spin text-amber-400" />
        <span className="font-mono text-xs text-text-muted shrink-0">
          {task.id}
        </span>
        <span className="truncate text-text-primary">{task.title}</span>
      </div>
      <div className="flex items-center gap-3 shrink-0 ml-3 text-xs text-text-muted">
        <span>{task.assignee}</span>
        <span className="font-mono text-amber-400">
          {elapsed !== null ? formatDuration(elapsed) : "-"}
        </span>
      </div>
    </Link>
  );
}

export default function OrgOverviewPage() {
  const { orgName, org, isLoading } = useCurrentOrg();
  const links = useOrgLinks();
  const { data: status } = useStatus();
  const { data: tasks } = useTasks({ organization: orgName });
  const { data: activeTasks } = useTasks({
    organization: orgName,
    status: "in_progress",
  });
  const deleteMut = useDeleteOrganization();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [showEdit, setShowEdit] = useState(false);
  const [showAddAgent, setShowAddAgent] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [descExpanded, setDescExpanded] = useState(false);

  if (isLoading || !org) {
    return (
      <>
        <BreadcrumbBar items={[{ label: "Overview" }]} />
        <div className="p-4 md:p-6">
          <PageSkeleton variant="dashboard" />
        </div>
      </>
    );
  }

  const statusCounts: Record<TaskStatus, number> = {
    open: 0,
    in_progress: 0,
    failed: 0,
    done: 0,
    canceled: 0,
  };
  tasks?.forEach((t) => {
    statusCounts[t.status]++;
  });

  const totalTokens = org.consumed_input_tokens + org.consumed_output_tokens;

  const handleDelete = async () => {
    try {
      await deleteMut.mutateAsync(orgName);
      toast("Organization deleted", "success");
      navigate("/");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to delete", "error");
    }
    setShowDelete(false);
  };

  return (
    <>
      <BreadcrumbBar items={[{ label: "Overview" }]} />
      <div className="space-y-6 p-4 md:p-6">
        {/* Org Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-text-primary">{org.name}</h1>
            <p className="mt-1 text-xs text-text-muted font-mono">
              {org.workspace_path}
            </p>
          </div>
          <div className="flex gap-1">
            <button
              onClick={() => setShowEdit(true)}
              className="rounded p-1.5 text-text-muted hover:bg-surface-overlay hover:text-text-secondary"
            >
              <Pencil size={14} />
            </button>
            <button
              onClick={() => setShowDelete(true)}
              className="rounded p-1.5 text-text-muted hover:bg-surface-overlay hover:text-red-400"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>

        {/* Description */}
        {org.description && (() => {
          const descriptionLines = org.description.split("\n").length;
          const descriptionLong = descriptionLines > 5;
          return (
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
                    ? "max-h-32 overflow-hidden relative after:absolute after:bottom-0 after:left-0 after:right-0 after:h-8 after:bg-gradient-to-t after:from-surface"
                    : ""
                }`}
              >
                <MarkdownRenderer content={org.description} />
              </div>
            </div>
          );
        })()}

        {/* Metrics */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricCard
            icon={Zap}
            label="Workers"
            value={
              status
                ? `${status.active_workers}/${status.max_concurrency}`
                : "-"
            }
          />
          <MetricCard
            icon={DollarSign}
            label="Org Cost"
            value={formatCost(org.total_cost)}
          />
          <MetricCard
            icon={Hash}
            label="Tokens"
            value={formatTokens(totalTokens)}
            subtext={`${formatTokens(org.consumed_input_tokens)} in / ${formatTokens(org.consumed_output_tokens)} out`}
          />
          <MetricCard
            icon={Loader2}
            label="Active"
            value={String(statusCounts.in_progress)}
            subtext={`${statusCounts.open} queued`}
          />
        </div>

        {/* Task Status Cards */}
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {(
            ["open", "in_progress", "failed", "done", "canceled"] as TaskStatus[]
          ).map((s) => {
            const config = statusConfig[s];
            const Icon = config.icon;
            return (
              <Link
                key={s}
                to={`${links.tasks()}?status=${s}`}
                className={`flex items-center gap-3 rounded-lg border p-3 transition-all hover:brightness-110 ${config.bg}`}
              >
                <Icon
                  size={16}
                  className={`${config.color} ${s === "in_progress" ? "animate-spin" : ""}`}
                />
                <div>
                  <div className="text-lg font-bold text-text-primary">
                    {statusCounts[s]}
                  </div>
                  <div className="text-[11px] text-text-muted">
                    {config.label}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Agent Hierarchy */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                Agent Hierarchy
              </h2>
              <button
                onClick={() => setShowAddAgent(true)}
                className="flex items-center gap-1.5 rounded-md bg-primary-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-primary-500"
              >
                <Plus size={14} /> Add Agent
              </button>
            </div>
            <AgentTree agents={org.agents} organization={orgName} />
          </div>

          {/* Active Tasks */}
          <div className="rounded-lg border border-border-default">
            <div className="flex items-center justify-between border-b border-border-default px-4 py-3">
              <h2 className="text-sm font-semibold text-text-primary">
                Active Tasks
              </h2>
              {activeTasks && activeTasks.length > 0 && (
                <Link
                  to={`${links.tasks()}?status=in_progress`}
                  className="text-xs text-primary-400 hover:text-primary-300 transition-colors"
                >
                  View all
                </Link>
              )}
            </div>
            <div className="divide-y divide-border-subtle">
              {activeTasks && activeTasks.length > 0 ? (
                activeTasks.map((task) => (
                  <ActiveTaskRow key={task.id} task={task} />
                ))
              ) : (
                <div className="px-4 py-8 text-center text-sm text-text-muted">
                  No tasks in progress
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <OrgForm
        mode="edit"
        organization={org}
        open={showEdit}
        onClose={() => setShowEdit(false)}
      />

      <AgentForm
        mode="create"
        organization={orgName}
        open={showAddAgent}
        onClose={() => setShowAddAgent(false)}
      />

      <ConfirmDialog
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={handleDelete}
        title="Delete Organization"
        message={`This will permanently delete "${orgName}" and all associated agents, tasks, runs, and chat sessions.`}
        confirmLabel="Delete"
        destructive
        loading={deleteMut.isPending}
      />
    </>
  );
}
