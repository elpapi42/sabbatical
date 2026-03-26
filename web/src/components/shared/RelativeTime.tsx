import { formatRelativeTime, formatAbsoluteTime } from "@/lib/format";
import { useRelativeTimeRefresh } from "@/lib/hooks";

interface Props {
  datetime: string;
  className?: string;
}

export default function RelativeTime({ datetime, className = "" }: Props) {
  useRelativeTimeRefresh();

  return (
    <time
      dateTime={datetime}
      title={formatAbsoluteTime(datetime)}
      className={`text-neutral-400 ${className}`}
    >
      {formatRelativeTime(datetime)}
    </time>
  );
}
