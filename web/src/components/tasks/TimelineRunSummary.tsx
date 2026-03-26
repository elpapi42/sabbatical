import { Link } from "react-router";
import type { TimelineRunSummary as TRunSummary } from "@/api/types";
import { useOrgLinks } from "@/lib/orgLinks";
import StatusBadge from "@/components/shared/StatusBadge";
import CostDisplay from "@/components/shared/CostDisplay";
import { formatDuration } from "@/lib/format";
import { ArrowRight } from "lucide-react";

interface Props {
  run: TRunSummary;
  taskId: string;
}

export default function TimelineRunSummary({ run, taskId }: Props) {
  const links = useOrgLinks();

  return (
    <div className="rounded-md border border-dashed border-border-default bg-surface-raised/50 px-4 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-text-muted">
            {run.run_id}
          </span>
          <span className="text-sm text-text-secondary">{run.agent}</span>
          <StatusBadge status={run.status} size="sm" />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-text-muted">
            {formatDuration(run.duration_seconds)}
          </span>
          <CostDisplay value={run.cost} className="text-xs" />
          <Link
            to={links.run(taskId, run.run_id)}
            className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300"
          >
            View Details <ArrowRight size={12} />
          </Link>
        </div>
      </div>
    </div>
  );
}
