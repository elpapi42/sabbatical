import { useParams } from "react-router";
import BreadcrumbBar from "@/components/layout/BreadcrumbBar";
import RunDetail from "@/components/runs/RunDetail";
import { useOrgLinks } from "@/lib/orgLinks";

export default function RunDetailPage() {
  const { id, runId } = useParams<{ id: string; runId: string }>();
  const links = useOrgLinks();
  if (!id || !runId) return null;

  return (
    <>
      <BreadcrumbBar
        items={[
          { label: "Tasks", to: links.tasks() },
          { label: id, to: links.task(id) },
          { label: `Run ${runId}` },
        ]}
      />
      <div className="p-4 md:p-6">
        <RunDetail runId={runId} taskId={id} />
      </div>
    </>
  );
}
