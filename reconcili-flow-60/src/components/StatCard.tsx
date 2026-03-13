import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: string;
  trend?: string;
  icon?: LucideIcon;
  className?: string;
}

export default function StatCard({ title, value, trend, icon: Icon, className }: StatCardProps) {
  return (
    <div className={cn(
      "bg-card rounded-2xl p-6 shadow-card transition-all duration-300 hover:-translate-y-1 hover:shadow-card-hover relative overflow-hidden group",
      className
    )}>
      {/* Top gradient bar */}
      <div className="absolute top-0 left-0 right-0 h-1 gradient-primary" />
      
      <div className="flex justify-between items-center mb-2">
        <span className="text-[13px] text-muted-foreground">{title}</span>
        {Icon && <Icon className="w-4 h-4 text-primary" />}
      </div>
      <div className="text-[28px] font-semibold text-card-foreground">{value}</div>
      {trend && (
        <div className="mt-2 text-xs text-success">{trend}</div>
      )}
    </div>
  );
}
