import { cn } from "@/lib/utils";

interface PhaseBadgeProps {
  phase: string;
  label: string;
  icon: React.ReactNode;
  variant: "f0" | "f1" | "f2" | "f3" | "f4";
}

const variantColors: Record<string, string> = {
  f0: "border-l-muted-foreground",
  f1: "border-l-success",
  f2: "border-l-warning",
  f3: "border-l-[hsl(24,95%,53%)]",
  f4: "border-l-destructive",
};

export default function PhaseBadge({ label, icon, variant }: PhaseBadgeProps) {
  return (
    <div className={cn(
      "px-4 py-2 rounded-full text-xs font-medium flex items-center gap-2 bg-card shadow-card border-l-[3px]",
      variantColors[variant]
    )}>
      {icon}
      {label}
    </div>
  );
}
