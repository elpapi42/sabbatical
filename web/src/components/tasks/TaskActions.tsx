import { useState } from "react";
import {
  Pause,
  CheckCircle2,
  RotateCcw,
  RefreshCw,
  XCircle,
} from "lucide-react";
import type { TaskDetail } from "@/api/types";
import { useAgents } from "@/api/queries";
import {
  usePreemptTask,
  useDoneTask,
  useReopenTask,
  useRetryTask,
  useCancelTask,
} from "@/api/mutations";
import { useToast } from "@/components/shared/Toast";
import ConfirmDialog from "@/components/shared/ConfirmDialog";

interface Props {
  task: TaskDetail;
}

export default function TaskActions({ task }: Props) {
  const { toast } = useToast();
  const preemptMut = usePreemptTask();
  const doneMut = useDoneTask();
  const reopenMut = useReopenTask();
  const retryMut = useRetryTask();
  const cancelMut = useCancelTask();
  const { data: agents } = useAgents(task.organization);

  const [showCancel, setShowCancel] = useState(false);
  const [showRetry, setShowRetry] = useState(false);
  const [retryAgent, setRetryAgent] = useState("");

  const { status, assignee } = task;
  const isUser = assignee === "user";

  const action = async (
    name: string,
    fn: () => Promise<unknown>,
  ) => {
    try {
      await fn();
    } catch (err) {
      toast(err instanceof Error ? err.message : `${name} failed`, "error");
    }
  };

  const btnClass =
    "flex items-center gap-1.5 rounded-md border border-neutral-700 px-3 py-1.5 text-xs font-medium text-neutral-300 hover:bg-neutral-800 transition-colors disabled:opacity-40";

  const buttons: React.ReactNode[] = [];

  if (status === "in_progress") {
    buttons.push(
      <button
        key="preempt"
        className={btnClass}
        onClick={() => action("Preempt", () => preemptMut.mutateAsync(task.id))}
        disabled={preemptMut.isPending}
      >
        <Pause size={14} /> Preempt
      </button>,
    );
  }

  if ((status === "open" && isUser) || (status === "failed" && isUser)) {
    buttons.push(
      <button
        key="done"
        className={btnClass}
        onClick={() => action("Done", () => doneMut.mutateAsync(task.id))}
        disabled={doneMut.isPending}
      >
        <CheckCircle2 size={14} /> Done
      </button>,
    );
  }

  if (status === "done" || status === "failed") {
    buttons.push(
      <button
        key="reopen"
        className={btnClass}
        onClick={() => action("Reopen", () => reopenMut.mutateAsync(task.id))}
        disabled={reopenMut.isPending}
      >
        <RotateCcw size={14} /> Reopen
      </button>,
    );
  }

  if (status === "failed" || status === "done") {
    buttons.push(
      <button
        key="retry"
        className={btnClass}
        onClick={() => setShowRetry(true)}
      >
        <RefreshCw size={14} /> Retry
      </button>,
    );
  }

  if (status !== "done" && status !== "canceled") {
    buttons.push(
      <button
        key="cancel"
        className={`${btnClass} hover:!border-red-500/50 hover:!text-red-400`}
        onClick={() => setShowCancel(true)}
      >
        <XCircle size={14} /> Cancel
      </button>,
    );
  }

  if (buttons.length === 0) return null;

  const handleRetry = async () => {
    await action("Retry", () =>
      retryMut.mutateAsync({
        id: task.id,
        assignee: retryAgent || undefined,
      }),
    );
    setShowRetry(false);
  };

  const handleCancel = async () => {
    await action("Cancel", () => cancelMut.mutateAsync(task.id));
    setShowCancel(false);
  };

  return (
    <>
      <div className="flex flex-wrap gap-2">{buttons}</div>

      {/* Retry dialog with agent selection */}
      {showRetry && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-lg border border-neutral-700 bg-neutral-900 p-5 shadow-2xl">
            <h3 className="mb-3 text-lg font-semibold">Retry Task</h3>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-neutral-400">
                Assign to agent (leave empty for last agent)
              </label>
              <select
                value={retryAgent}
                onChange={(e) => setRetryAgent(e.target.value)}
                className="w-full rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm text-neutral-100 focus:border-primary-500 focus:outline-none"
              >
                <option value="">Last agent</option>
                {agents
                  ?.filter((a) => !a.is_removed)
                  .map((a) => (
                    <option key={a.name} value={a.name}>
                      {a.name}
                    </option>
                  ))}
              </select>
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowRetry(false)}
                className="rounded-md px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-800"
              >
                Cancel
              </button>
              <button
                onClick={handleRetry}
                disabled={retryMut.isPending}
                className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-500 disabled:opacity-50"
              >
                {retryMut.isPending ? "..." : "Retry"}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={showCancel}
        onClose={() => setShowCancel(false)}
        onConfirm={handleCancel}
        title="Cancel Task"
        message={`Cancel task ${task.id}? This action is permanent.${status === "in_progress" ? " The active run will be preempted." : ""}`}
        confirmLabel="Cancel Task"
        destructive
        loading={cancelMut.isPending}
      />
    </>
  );
}
