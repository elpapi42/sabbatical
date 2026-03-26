import { Outlet } from "react-router";
import OrgRail from "./OrgRail";
import OrgSidebar from "./OrgSidebar";
import { SidebarProvider } from "@/context/SidebarContext";
import { OrgProvider } from "@/context/OrgContext";
import { useStatus } from "@/api/queries";

function LayoutInner() {
  const { isError, failureCount } = useStatus();
  const serverDown = isError && failureCount >= 3;

  return (
    <div className="flex h-dvh min-h-0 bg-neutral-950">
      <OrgRail />
      <OrgProvider>
        <SidebarProvider>
          <OrgSidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            {serverDown && (
              <div className="shrink-0 border-b border-red-500/30 bg-red-500/10 px-4 py-2 text-center text-sm text-red-400">
                Unable to reach the Sabbatical server. Is it running? Run{" "}
                <code className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs">
                  sabbatical server up
                </code>{" "}
                to start.
              </div>
            )}
            <main className="flex-1 min-h-0 overflow-y-auto">
              <Outlet />
            </main>
          </div>
        </SidebarProvider>
      </OrgProvider>
    </div>
  );
}

export default function AppLayout() {
  return <LayoutInner />;
}
