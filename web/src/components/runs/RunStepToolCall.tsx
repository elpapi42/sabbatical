import { useState } from "react";
import { Wrench, ChevronDown, ChevronRight } from "lucide-react";
import type { ExecutionStep } from "@/api/types";

interface Props {
  step: ExecutionStep;
}

export default function RunStepToolCall({ step }: Props) {
  const [argsExpanded, setArgsExpanded] = useState(false);
  const [outputExpanded, setOutputExpanded] = useState(false);
  const [fullOutput, setFullOutput] = useState(false);

  const output = step.output ?? "";
  const isLongOutput = output.length > 500;
  const displayOutput = fullOutput ? output : output.slice(0, 500);

  return (
    <div className="rounded-md border border-amber-500/20 bg-amber-500/5">
      <div className="flex items-center gap-2 px-4 py-2.5 text-sm">
        <Wrench size={14} className="text-amber-400" />
        <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-xs font-medium text-amber-300">
          {step.tool}
        </span>
      </div>

      {step.arguments && (
        <div className="border-t border-amber-500/10">
          <button
            onClick={() => setArgsExpanded(!argsExpanded)}
            className="flex w-full items-center gap-2 px-4 py-2 text-xs text-neutral-400 hover:bg-amber-500/5"
          >
            {argsExpanded ? (
              <ChevronDown size={12} />
            ) : (
              <ChevronRight size={12} />
            )}
            Arguments
          </button>
          {argsExpanded && (
            <pre className="overflow-x-auto border-t border-amber-500/10 bg-neutral-900/50 px-4 py-3 text-xs text-neutral-300">
              {JSON.stringify(step.arguments, null, 2)}
            </pre>
          )}
        </div>
      )}

      {output && (
        <div className="border-t border-amber-500/10">
          <button
            onClick={() => setOutputExpanded(!outputExpanded)}
            className="flex w-full items-center gap-2 px-4 py-2 text-xs text-neutral-400 hover:bg-amber-500/5"
          >
            {outputExpanded ? (
              <ChevronDown size={12} />
            ) : (
              <ChevronRight size={12} />
            )}
            Output ({output.length} chars)
          </button>
          {outputExpanded && (
            <div className="border-t border-amber-500/10 bg-neutral-900/50 px-4 py-3">
              <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-neutral-300">
                {displayOutput}
                {isLongOutput && !fullOutput && "..."}
              </pre>
              {isLongOutput && (
                <button
                  onClick={() => setFullOutput(!fullOutput)}
                  className="mt-2 text-xs text-primary-400 hover:text-primary-300"
                >
                  {fullOutput ? "Show less" : "Show full output"}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
