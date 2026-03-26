import { Link } from "react-router";
import { ChevronRight, Menu } from "lucide-react";
import { useSidebar } from "@/context/SidebarContext";

export interface BreadcrumbItem {
  label: string;
  to?: string;
}

interface Props {
  items: BreadcrumbItem[];
}

export default function BreadcrumbBar({ items }: Props) {
  const { isMobile, toggle } = useSidebar();

  return (
    <header className="sticky top-0 z-20 flex h-12 shrink-0 items-center gap-3 border-b border-border-default bg-surface/80 px-4 backdrop-blur-md md:px-6">
      {isMobile && (
        <button
          onClick={toggle}
          className="rounded p-1 text-text-muted hover:bg-surface-overlay hover:text-text-secondary"
        >
          <Menu size={18} />
        </button>
      )}

      <nav className="flex min-w-0 items-center gap-1">
        {items.length === 1 ? (
          // Single item: render as page title
          <h1 className="text-sm font-semibold uppercase tracking-wider text-text-primary truncate">
            {items[0].label}
          </h1>
        ) : (
          // Multiple items: render as breadcrumb trail
          items.map((item, i) => (
            <span key={i} className="flex items-center gap-1 min-w-0">
              {i > 0 && (
                <ChevronRight
                  size={14}
                  className="shrink-0 text-text-muted"
                />
              )}
              {item.to ? (
                <Link
                  to={item.to}
                  className="truncate text-sm text-text-muted hover:text-text-primary transition-colors"
                >
                  {item.label}
                </Link>
              ) : (
                <span className="truncate text-sm font-medium text-text-primary">
                  {item.label}
                </span>
              )}
            </span>
          ))
        )}
      </nav>
    </header>
  );
}
