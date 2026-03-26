import { Link } from "react-router";
import { useRun } from "@/api/queries";
import { useOrgLinks } from "@/lib/orgLinks";
import StatusBadge from "@/components/shared/StatusBadge";
import CostDisplay from "@/components/shared/CostDisplay";
import TokenDisplay from "@/components/shared/TokenDisplay";
import PageSkeleton from "@/components/shared/PageSkeleton";
import { formatDuration } from "@/lib/format";
import RunStepReasoning from "./RunStepReasoning";
import RunStepToolCall from "./RunStepToolCall";
import RunStepFinalOutput from "./RunStepFinalOutput";

interface Props {
  runId: string;
  taskId: string;
}

export default function RunDetail({ runId, taskId }: Props) {
  const { data: run, isLoading } = useRun(runId);
  const links = useOrgLinks();

  if (isLoading || !run) return <PageSkeleton variant="detail" />;

  const steps = run.execution_steps;
  const reasoningCount = steps.filter(
    (s) => s.type === "llm_reasoning",
  ).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <h1 className="font-mono text-lg font-bold text-text-primary">
            {run.id}
          </h1>
          <StatusBadge status={run.status} size="md" />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-text-muted">
          <span>
            Task:{" "}
            <Link
              to={links.task(taskId)}
              className="text-primary-400 hover:text-primary-300"
            >
              {run.task_id}
            </Link>
          </span>
          <span>
            Agent:{" "}
            <Link
              to={links.agent(run.agent)}
              className="text-primary-400 hover:text-primary-300"
            >
              {run.agent}
            </Link>
          </span>
          <span>Model: {run.model_used ?? "default"}</span>
          <span>Duration: {formatDuration(run.duration_seconds)}</span>
        </div>
        <div className="mt-2 flex items-center gap-4 text-sm">
          <CostDisplay value={run.total_cost} />
          <span className="text-border-default">·</span>
          <span className="text-text-muted">
            Input: <TokenDisplay count={run.consumed_input_tokens} />
          </span>
          <span className="text-text-muted">
            Output: <TokenDisplay count={run.consumed_output_tokens} />
          </span>
        </div>
      </div>

      {/* Execution Steps */}
      <div>
        <h2 className="mb-3 text-xs font-semibold text-text-muted uppercase tracking-wider">
          Execution Steps ({steps.length})
        </h2>

        <div className="relative space-y-3 pl-10">
          <div className="absolute left-4 top-0 bottom-0 w-px bg-border-default" />

          {steps.map((step, i) => (
            <div key={i} className="relative">
              <div className="absolute -left-10 top-2.5 flex h-6 w-6 items-center justify-center rounded-full bg-surface-overlay text-xs font-mono text-text-muted">
                {step.step}
              </div>

              {step.type === "llm_reasoning" && (
                <RunStepReasoning
                  step={step}
                  defaultExpanded={
                    i === 0 ||
                    i === steps.length - 1 ||
                    reasoningCount <= 3
                  }
                />
              )}
              {step.type === "tool_call" && <RunStepToolCall step={step} />}
              {step.type === "final_output" && (
                <RunStepFinalOutput step={step} />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
