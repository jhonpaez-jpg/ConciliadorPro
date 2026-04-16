import { Calendar, FileSpreadsheet } from "lucide-react";
import { getMonthName } from "@/context/AppContext";

// ── Configuración visual por fase ─────────────────────────────────────────────
export const PHASE_CONFIG = {
  F1: { color: "#10b981", label: "F1 — Fast-Pass 1:1", icon: "⚡" },
  F2: { color: "#f59e0b", label: "F2 — Subset Sum N:N", icon: "⊞" },
  F3: { color: "#8b5cf6", label: "F3 — Tolerancia ±5 centavos", icon: "≈" },
  F4: { color: "#3b82f6", label: "F4 — Monto + Localidad", icon: "📍" },
  F5: { color: "#ef4444", label: "F5 — Monto Global", icon: "=" },
  F6: { color: "#f97316", label: "F6 — Subset Sum Global", icon: "⇉" },
  F7: { color: "#06b6d4", label: "F7 — Final Cleaning", icon: "⟶" },
  F7b: { color: "#84cc16", label: "F7b — Limpieza Final", icon: "🧹" },
} as const;

export type PhaseKey = keyof typeof PHASE_CONFIG;

// ── KPI mini-card ─────────────────────────────────────────────────────────────
interface KpiProps {
  value: string;
  label: string;
  color?: string;
}

export function PhaseKpi({ value, label, color }: KpiProps) {
  return (
    <div className="bg-[#f8fafc] rounded-2xl p-4 text-center">
      <div
        className="text-[22px] font-bold text-[#1e293b]"
        style={color ? { color } : {}}
      >
        {value}
      </div>
      <div className="text-[11px] text-[#64748b] mt-1 uppercase tracking-wide font-medium">
        {label}
      </div>
    </div>
  );
}

// ── Barra de progreso de fase ─────────────────────────────────────────────────
interface ProgressBarProps {
  pct: number;
  color: string;
  label: string;
  total: number;
  found: number;
}

export function PhaseProgressBar({
  pct,
  color,
  label,
  total,
  found,
}: ProgressBarProps) {
  return (
    <div className="bg-[#f8fafc] rounded-2xl p-4">
      <p className="text-xs text-[#64748b] mb-2">
        Contribución al total conciliado
      </p>
      <div className="w-full bg-[#e2e8f0] rounded-full h-3">
        <div
          className="h-3 rounded-full transition-all duration-700"
          style={{ width: `${Math.min(pct, 100)}%`, background: color }}
        />
      </div>
      <p className="text-xs text-[#64748b] mt-2">
        {label} encontró{" "}
        <strong className="text-[#1e293b]">{found.toLocaleString()}</strong> de{" "}
        <strong className="text-[#1e293b]">{total.toLocaleString()}</strong>{" "}
        conciliados totales
      </p>
    </div>
  );
}

// ── Wrapper de sección vacía ──────────────────────────────────────────────────
interface EmptyProps {
  phase: PhaseKey;
}

export function PhaseEmpty({ phase }: EmptyProps) {
  const cfg = PHASE_CONFIG[phase];
  return (
    <div
      className="bg-white rounded-[20px] p-12 text-center"
      style={{
        boxShadow: "0 4px 20px rgba(0,0,0,0.04)",
        borderTop: `5px solid ${cfg.color}`,
      }}
    >
      <FileSpreadsheet
        className="w-14 h-14 mx-auto mb-4"
        style={{ color: cfg.color, opacity: 0.3 }}
      />
      <h3 className="text-lg font-bold text-[#1e293b] mb-2">{cfg.label}</h3>
      <p className="text-sm text-[#64748b]">
        Ejecuta una conciliación para ver resultados de esta fase.
      </p>
    </div>
  );
}

// ── Header de mes ─────────────────────────────────────────────────────────────
interface MonthHeaderProps {
  monthIndex: number;
  year: number;
  isFallback: boolean;
}

export function MonthHeader({
  monthIndex,
  year,
  isFallback,
}: MonthHeaderProps) {
  return (
    <div className="flex items-center gap-2 flex-wrap mb-1">
      <div className="flex items-center gap-2 text-[#64748b] text-sm">
        <Calendar className="w-4 h-4 text-[#667eea]" />
        <span>
          Datos de{" "}
          <strong className="text-[#1e293b]">
            {getMonthName(monthIndex)} {year}
          </strong>
        </span>
      </div>
      {isFallback && (
        <span className="px-3 py-1 rounded-full text-[11px] font-medium bg-amber-50 text-amber-600 border border-amber-200">
          ⚠ Última conciliación disponible
        </span>
      )}
    </div>
  );
}

// ── Hero card principal ───────────────────────────────────────────────────────
interface PhaseHeroCardProps {
  phase: PhaseKey;
  desc: React.ReactNode;
  cuenta: string;
  children: React.ReactNode; // KPIs + barra
}

export function PhaseHeroCard({
  phase,
  desc,
  cuenta,
  children,
}: PhaseHeroCardProps) {
  const cfg = PHASE_CONFIG[phase];
  return (
    <div
      className="bg-white rounded-[20px] p-7 space-y-6"
      style={{
        boxShadow: "0 4px 20px rgba(0,0,0,0.04)",
        borderTop: `5px solid ${cfg.color}`,
      }}
    >
      {/* Título con icono */}
      <div>
        <h3 className="text-xl font-bold text-[#1e293b] mb-2 flex items-center gap-2">
          <span style={{ color: cfg.color }}>{cfg.icon}</span>
          {cfg.label}
        </h3>
        <p className="text-[13px] text-[#64748b] leading-relaxed">{desc}</p>
        <p className="text-[11px] text-[#94a3b8] mt-1">Cuenta: {cuenta}</p>
      </div>
      {children}
    </div>
  );
}
