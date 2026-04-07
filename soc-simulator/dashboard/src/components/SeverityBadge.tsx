import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

const band = (
  severity: number
): { label: string; className: string } => {
  if (severity <= 3)
    return {
      label: "LOW",
      className: "border-zinc-600 bg-zinc-800/80 text-zinc-300",
    };
  if (severity <= 6)
    return {
      label: "MEDIUM",
      className: "border-amber-600/60 bg-amber-950/50 text-amber-300",
    };
  if (severity <= 8)
    return {
      label: "HIGH",
      className: "border-orange-600/60 bg-orange-950/40 text-orange-300",
    };
  return {
    label: "CRITICAL",
    className: "border-destructive/60 bg-destructive/20 text-destructive",
  };
};

export function SeverityBadge({
  severity,
  className,
}: {
  severity: number;
  className?: string;
}) {
  const { label, className: bandClass } = band(
    Math.max(0, Math.min(10, severity))
  );
  return (
    <Badge
      variant="outline"
      className={cn(bandClass, "font-data tabular-nums", className)}
    >
      {severity}{" "}
      <span className="font-sans text-[10px] font-normal opacity-90">
        {label}
      </span>
    </Badge>
  );
}
