import {
  Circle,
  Loader2,
  XCircle,
  CheckCircle2,
  Ban,
  type LucideIcon,
} from "lucide-react";
import type { TaskStatus, RunStatus } from "@/api/types";
import { STATUS_LABELS } from "@/lib/constants";

const iconMap: Record<string, LucideIcon> = {
  open: Circle,
  in_progress: Loader2,
  running: Loader2,
  failed: XCircle,
  done: CheckCircle2,
  success: CheckCircle2,
  canceled: Ban,
  preempted: Ban,
};

const colorClasses: Record<string, string> = {
  open: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  in_progress: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  running: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  failed: "bg-red-500/15 text-red-400 border-red-500/30",
  done: "bg-green-500/15 text-green-400 border-green-500/30",
  success: "bg-green-500/15 text-green-400 border-green-500/30",
  canceled: "bg-neutral-500/15 text-neutral-400 border-neutral-500/30",
  preempted: "bg-neutral-500/15 text-neutral-400 border-neutral-500/30",
};

interface Props {
  status: TaskStatus | RunStatus;
  size?: "sm" | "md";
}

export default function StatusBadge({ status, size = "sm" }: Props) {
  const Icon = iconMap[status] ?? Circle;
  const colors = colorClasses[status] ?? colorClasses.open;
  const isSpinning = status === "in_progress" || status === "running";
  const sizeClasses =
    size === "sm" ? "text-xs px-2 py-0.5 gap-1" : "text-sm px-2.5 py-1 gap-1.5";
  const iconSize = size === "sm" ? 12 : 14;

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${colors} ${sizeClasses}`}
    >
      <Icon size={iconSize} className={isSpinning ? "animate-spin" : ""} />
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}
