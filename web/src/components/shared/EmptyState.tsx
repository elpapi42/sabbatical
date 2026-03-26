import type { LucideIcon } from "lucide-react";

interface Props {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-overlay">
        <Icon size={28} className="text-text-muted" />
      </div>
      <h3 className="mb-1 text-base font-medium text-text-primary">{title}</h3>
      {description && (
        <p className="mb-5 max-w-sm text-sm text-text-muted">{description}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
