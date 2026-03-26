import { Flag } from "lucide-react";
import type { ExecutionStep } from "@/api/types";
import MarkdownRenderer from "@/components/shared/MarkdownRenderer";

interface Props {
  step: ExecutionStep;
}

export default function RunStepFinalOutput({ step }: Props) {
  return (
    <div className="rounded-md border-2 border-green-500/30 bg-green-500/5">
      <div className="flex items-center gap-2 px-4 py-2.5 text-sm text-green-300">
        <Flag size={14} />
        <span className="font-medium">Final Output</span>
      </div>
      <div className="border-t border-green-500/20 px-4 py-3">
        <MarkdownRenderer content={step.content ?? ""} />
      </div>
    </div>
  );
}
