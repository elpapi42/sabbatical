import { Routes, Route } from "react-router";
import AppLayout from "@/components/layout/AppLayout";
import OrgRedirect from "@/components/layout/OrgRedirect";
import OrgOverviewPage from "@/pages/OrgOverviewPage";
import AgentDetailPage from "@/pages/AgentDetailPage";
import TasksPage from "@/pages/TasksPage";
import TaskDetailPage from "@/pages/TaskDetailPage";
import RunDetailPage from "@/pages/RunDetailPage";
import ChatListPage from "@/pages/ChatListPage";
import ChatPage from "@/pages/ChatPage";

export default function App() {
  return (
    <Routes>
      {/* Root: redirect to first org */}
      <Route index element={<OrgRedirect />} />

      {/* Org-scoped layout */}
      <Route path="org/:name" element={<AppLayout />}>
        <Route index element={<OrgOverviewPage />} />
        <Route path="agents/:agentName" element={<AgentDetailPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="tasks/:id" element={<TaskDetailPage />} />
        <Route path="tasks/:id/runs/:runId" element={<RunDetailPage />} />
        <Route path="chat" element={<ChatListPage />} />
        <Route path="chat/:id" element={<ChatPage />} />
      </Route>
    </Routes>
  );
}
