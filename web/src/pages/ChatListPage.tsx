import { useState } from "react";
import { useNavigate } from "react-router";
import { Plus } from "lucide-react";
import BreadcrumbBar from "@/components/layout/BreadcrumbBar";
import SessionList from "@/components/chat/SessionList";
import { useCurrentOrg } from "@/context/OrgContext";
import { useOrgLinks } from "@/lib/orgLinks";
import { useCreateSession } from "@/api/mutations";
import { useKeyboardShortcut } from "@/lib/hooks";

export default function ChatListPage() {
  const navigate = useNavigate();
  const { orgName } = useCurrentOrg();
  const links = useOrgLinks();
  const createMut = useCreateSession();
  const [creating, setCreating] = useState(false);

  useKeyboardShortcut("n", () => handleCreate());

  const handleCreate = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const session = await createMut.mutateAsync({
        organization_scope: orgName,
      });
      navigate(links.chatSession(session.id));
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <BreadcrumbBar items={[{ label: "Chat" }]} />
      <div className="p-4 md:p-6">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-text-primary">Chat Sessions</h1>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="flex items-center gap-1.5 rounded-md bg-primary-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500 disabled:opacity-50"
          >
            <Plus size={16} /> {creating ? "Creating..." : "New Chat"}
          </button>
        </div>

        <SessionList onNew={handleCreate} />
      </div>
    </>
  );
}
