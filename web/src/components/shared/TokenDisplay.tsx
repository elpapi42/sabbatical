import { formatTokens } from "@/lib/format";

interface Props {
  count: number;
  className?: string;
}

export default function TokenDisplay({ count, className = "" }: Props) {
  return (
    <span className={`font-mono text-neutral-400 ${className}`} title={count.toLocaleString()}>
      {formatTokens(count)}
    </span>
  );
}
