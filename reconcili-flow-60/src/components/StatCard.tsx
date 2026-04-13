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
      "bg-white rounded-[20px] p-[22px] relative overflow-hidden transition-all duration-300",
      "hover:-translate-y-1",
      className
    )}
    style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.04)" }}
    onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 8px 30px rgba(102,126,234,0.18)")}
    onMouseLeave={e => (e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.04)")}
    >
      {/* Barra superior gradiente — exacta del Index.html */}
      <div className="absolute top-0 left-0 right-0 h-1"
           style={{ background: "linear-gradient(90deg, #667eea, #764ba2)" }} />

      <div className="flex justify-between items-center mb-2">
        <span className="text-[12px] text-[#64748b]">{title}</span>
        {Icon && <Icon className="w-[15px] h-[15px]" style={{ color: "#667eea" }} />}
      </div>
      <div className="text-[26px] font-bold text-[#1e293b]">{value}</div>
      {trend && (
        <div className="mt-1.5 text-[11px] text-[#10b981]">{trend}</div>
      )}
    </div>
  );
}
