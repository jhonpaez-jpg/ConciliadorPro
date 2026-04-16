import { cn } from "@/lib/utils";

interface PhaseBadgeProps {
  phase: string;
  label: string;
  icon: React.ReactNode;
  variant: "f0" | "f1" | "f2" | "f3" | "f4" | "f5" | "f6" | "f7" | "f7b";
}

// Colores exactos del Index.html
const BORDER_COLORS: Record<string, string> = {
  f0: "border-l-[#94a3b8]",
  f1: "border-l-[#10b981]",
  f2: "border-l-[#f59e0b]",
  f3: "border-l-[#8b5cf6]",
  f4: "border-l-[#3b82f6]",
  f5: "border-l-[#ef4444]",
  f6: "border-l-[#f97316]",
  f7: "border-l-[#06b6d4]",
  f7b: "border-l-[#84cc16]",
};

const TEXT_COLORS: Record<string, string> = {
  f0: "text-slate-500",
  f1: "text-emerald-800",
  f2: "text-amber-800",
  f3: "text-violet-800",
  f4: "text-blue-800",
  f5: "text-red-800",
  f6: "text-orange-800",
  f7: "text-cyan-800",
  f7b: "text-lime-800",
};

export default function PhaseBadge({ label, icon, variant }: PhaseBadgeProps) {
  return (
    <div
      className={cn(
        "px-3.5 py-1.5 rounded-full text-xs font-semibold flex items-center gap-2",
        "bg-white shadow-[0_2px_8px_rgba(0,0,0,0.06)] border-l-[3px]",
        BORDER_COLORS[variant] ?? "border-l-border",
        TEXT_COLORS[variant] ?? "text-muted-foreground",
      )}
    >
      {icon}
      {label}
    </div>
  );
}
