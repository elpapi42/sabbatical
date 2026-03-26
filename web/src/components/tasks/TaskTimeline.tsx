import type { TimelineEntry } from "@/api/types";
import TimelineComment from "./TimelineComment";
import TimelineRunSummary from "./TimelineRunSummary";

interface Props {
  timeline: TimelineEntry[];
  taskId: string;
  organization: string;
}

export default function TaskTimeline({ timeline, taskId, organization }: Props) {
  if (timeline.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-neutral-600">
        No activity yet
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {timeline.map((entry, i) => {
        if (entry.type === "comment") {
          return (
            <TimelineComment
              key={`comment-${i}`}
              comment={entry}
              organization={organization}
            />
          );
        }
        return (
          <TimelineRunSummary
            key={`run-${entry.run_id}`}
            run={entry}
            taskId={taskId}
          />
        );
      })}
    </div>
  );
}
