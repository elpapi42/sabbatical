import { useParams } from "react-router";
import BreadcrumbBar from "@/components/layout/BreadcrumbBar";
import TaskDetail from "@/components/tasks/TaskDetail";
import { useOrgLinks } from "@/lib/orgLinks";

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const links = useOrgLinks();
  if (!id) return null;

  return (
    <>
      <BreadcrumbBar
        items={[{ label: "Tasks", to: links.tasks() }, { label: id }]}
      />
      <div className="p-4 md:p-6">
        <TaskDetail taskId={id} />
      </div>
    </>
  );
}
