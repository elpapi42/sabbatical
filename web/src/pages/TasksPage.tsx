import { useState } from "react";
import { useNavigate } from "react-router";
import { Plus } from "lucide-react";
import BreadcrumbBar from "@/components/layout/BreadcrumbBar";
import TaskList from "@/components/tasks/TaskList";
import TaskForm from "@/components/tasks/TaskForm";
import { useCurrentOrg } from "@/context/OrgContext";
import { useOrgLinks } from "@/lib/orgLinks";
import { useKeyboardShortcut } from "@/lib/hooks";

export default function TasksPage() {
  const navigate = useNavigate();
  const { orgName } = useCurrentOrg();
  const links = useOrgLinks();
  const [showCreate, setShowCreate] = useState(false);

  useKeyboardShortcut("n", () => setShowCreate(true));

  return (
    <>
      <BreadcrumbBar items={[{ label: "Tasks" }]} />
      <div className="p-4 md:p-6">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-text-primary">Tasks</h1>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 rounded-md bg-primary-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500"
          >
            <Plus size={16} /> New Task
          </button>
        </div>

        <TaskList />

        <TaskForm
          open={showCreate}
          onClose={() => setShowCreate(false)}
          onSuccess={(id) => {
            // Navigate handled by TaskForm closing + cache invalidation
            navigate(links.task(id));
          }}
          organization={orgName!}
        />
      </div>
    </>
  );
}
