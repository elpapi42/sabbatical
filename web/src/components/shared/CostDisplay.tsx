import { formatCost } from "@/lib/format";

interface Props {
  value: number;
  className?: string;
}

export default function CostDisplay({ value, className = "" }: Props) {
  return (
    <span className={`font-mono text-neutral-300 ${className}`}>
      {formatCost(value)}
    </span>
  );
}
