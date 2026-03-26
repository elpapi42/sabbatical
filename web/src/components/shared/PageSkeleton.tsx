import type React from "react";

type Variant = "dashboard" | "list" | "detail" | "chat";

function S({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <S className="h-14 w-full" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {[...Array(5)].map((_, i) => (
          <S key={i} className="h-20" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <S className="h-64" />
        <S className="h-64" />
      </div>
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <S className="h-9 w-48" />
        <S className="h-9 w-32" />
        <div className="flex-1" />
        <S className="h-9 w-28" />
      </div>
      <div className="space-y-0 overflow-hidden rounded-lg border border-border-default">
        <S className="h-10 rounded-none" />
        {[...Array(6)].map((_, i) => (
          <S key={i} className="h-11 rounded-none border-t border-border-subtle" />
        ))}
      </div>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <S className="h-7 w-80" />
        <S className="h-4 w-64" />
      </div>
      <S className="h-32" />
      <div className="flex gap-2">
        <S className="h-9 w-24" />
        <S className="h-9 w-24" />
        <S className="h-9 w-24" />
      </div>
      <div className="space-y-3">
        {[...Array(4)].map((_, i) => (
          <S key={i} className="h-20" />
        ))}
      </div>
    </div>
  );
}

function ChatSkeleton() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 p-4">
        <div className="flex justify-end">
          <S className="h-16 w-2/3" />
        </div>
        <div className="flex justify-start">
          <S className="h-24 w-3/4" />
        </div>
        <div className="flex justify-end">
          <S className="h-12 w-1/2" />
        </div>
      </div>
      <div className="border-t border-border-default p-4">
        <S className="h-12" />
      </div>
    </div>
  );
}

const variants: Record<Variant, () => React.ReactNode> = {
  dashboard: DashboardSkeleton,
  list: ListSkeleton,
  detail: DetailSkeleton,
  chat: ChatSkeleton,
};

export default function PageSkeleton({
  variant = "detail",
}: {
  variant?: Variant;
}) {
  const Component = variants[variant];
  return <Component />;
}
