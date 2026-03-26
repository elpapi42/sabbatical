import { useParams } from "react-router";
import BreadcrumbBar from "@/components/layout/BreadcrumbBar";
import ChatInterface from "@/components/chat/ChatInterface";
import { useOrgLinks } from "@/lib/orgLinks";

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const links = useOrgLinks();
  if (!id) return null;

  return (
    <div className="flex h-full flex-col">
      <BreadcrumbBar
        items={[{ label: "Chat", to: links.chat() }, { label: id }]}
      />
      <div className="flex-1 min-h-0">
        <ChatInterface sessionId={id} />
      </div>
    </div>
  );
}
