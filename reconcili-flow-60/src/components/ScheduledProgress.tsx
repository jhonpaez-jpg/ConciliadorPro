import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { CalendarClock, CheckCircle, XCircle, Loader2, Clock, Trash2, ChevronDown, ChevronUp, Timer } from "lucide-react";
import { useReconciliation } from "@/context/ReconciliationContext";

// ── Tipos ─────────────────────────────────────────────────────────────────────
interface EstadoBackend {
  fase: string;
  mensaje: string;
  conciliados: number;
  pendientes: number;
  tasa: number;
  reporte?: string;
}

interface ScheduledItem {
  id: number;
  fecha: string;
  hora: string;
  archivo: string;
  estado: "PENDIENTE" | "EJECUTANDO" | "COMPLETADO" | "ERROR" | "CANCELADO";
  creado_en: string;
  ejecutado_en?: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatCountdown(secs: number): string {
  if (secs <= 0) return "Ahora";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function getProgressPct(msg: string): number {
  const m = msg.toLowerCase();
  if (!msg || m.includes("subiendo"))                   return 5;
  if (m.includes("leyendo") || m.includes("filtrando")) return 10;
  if (m.includes("insertando"))                         return 18;
  if (m.includes("f1-f4") && m.includes("[")) {
    const match = m.match(/\[(\d+)\/(\d+)\]/);
    if (match) return Math.round(22 + (parseInt(match[1]) / parseInt(match[2])) * 38);
    return 30;
  }
  if (m.includes("f1-f4"))                              return 22;
  if (m.includes("f6") || m.includes("subset"))         return 65;
  if (m.includes("f5") || m.includes("monto puro"))     return 80;
  if (m.includes("generando reporte"))                   return 90;
  if (m.includes("procesando"))                         return 15;
  return 50;
}

const ESTADO_CONFIG = {
  PENDIENTE:   { color: "#667eea", bg: "rgba(102,126,234,0.08)", label: "Pendiente",  icon: Clock },
  EJECUTANDO:  { color: "#f59e0b", bg: "rgba(245,158,11,0.08)",  label: "Ejecutando", icon: Loader2 },
  COMPLETADO:  { color: "#10b981", bg: "rgba(16,185,129,0.08)",  label: "Completado", icon: CheckCircle },
  ERROR:       { color: "#ef4444", bg: "rgba(239,68,68,0.08)",   label: "Error",      icon: XCircle },
  CANCELADO:   { color: "#94a3b8", bg: "rgba(148,163,184,0.08)", label: "Cancelado",  icon: XCircle },
};

// ── Fila de una ejecución programada ─────────────────────────────────────────
function ScheduledRow({
  item,
  estado,
  onCancel,
  onRefresh,
}: {
  item: ScheduledItem;
  estado: EstadoBackend | null;
  onCancel: (id: number) => void;
  onRefresh: () => void;
}) {
  const [expanded, setExpanded] = useState(item.estado === "EJECUTANDO");
  const [countdown, setCountdown] = useState(() => {
    const dt = new Date(`${item.fecha}T${item.hora}:00`);
    return Math.max(0, Math.floor((dt.getTime() - Date.now()) / 1000));
  });

  // Cuenta regresiva
  useEffect(() => {
    if (item.estado !== "PENDIENTE" || countdown <= 0) return;
    const id = setInterval(() => setCountdown(s => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [item.estado, countdown]);

  const cfg = ESTADO_CONFIG[item.estado] ?? ESTADO_CONFIG.PENDIENTE;
  const IconComp = cfg.icon;
  const pct = item.estado === "EJECUTANDO" && estado ? getProgressPct(estado.mensaje) : 0;
  const isPast = countdown <= 0 && item.estado === "PENDIENTE";

  return (
    <div
      className="rounded-2xl border overflow-hidden transition-all"
      style={{ borderColor: cfg.color + "40", background: cfg.bg }}
    >
      {/* Fila principal */}
      <div className="flex items-center gap-3 p-4">
        {/* Icono de estado */}
        <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
             style={{ background: cfg.color + "20" }}>
          <IconComp
            className={`w-4 h-4 ${item.estado === "EJECUTANDO" ? "animate-spin" : ""}`}
            style={{ color: cfg.color }}
          />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-[#1e293b] truncate">{item.archivo}</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide"
                  style={{ background: cfg.color + "20", color: cfg.color }}>
              {cfg.label}
            </span>
            {item.estado === "PENDIENTE" && (
              <span className="flex items-center gap-1 text-xs font-mono"
                    style={{ color: isPast ? "#f59e0b" : "#667eea" }}>
                <Timer className="w-3 h-3" />
                {isPast ? "Iniciando..." : formatCountdown(countdown)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-0.5 text-xs text-[#64748b] flex-wrap">
            <span>
              <CalendarClock className="w-3 h-3 inline mr-1" />
              {item.fecha} a las <strong className="text-[#1e293b]">{item.hora}</strong>
            </span>
            {item.ejecutado_en && (
              <span>Ejecutado: {item.ejecutado_en}</span>
            )}
            <span className="opacity-60">Creado: {item.creado_en}</span>
          </div>
        </div>

        {/* Acciones */}
        <div className="flex items-center gap-2 shrink-0">
          {item.estado === "PENDIENTE" && (
            <button
              onClick={() => onCancel(item.id)}
              className="p-1.5 rounded-lg hover:bg-red-50 text-[#94a3b8] hover:text-red-500 transition-colors"
              title="Cancelar"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
          {(item.estado === "EJECUTANDO" || item.estado === "COMPLETADO") && (
            <button
              onClick={() => setExpanded(v => !v)}
              className="p-1.5 rounded-lg hover:bg-white/60 text-[#94a3b8] transition-colors"
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Barra de progreso — solo cuando ejecuta */}
      {item.estado === "EJECUTANDO" && (
        <div className="px-4 pb-2">
          <div className="w-full bg-white/60 rounded-full h-2 overflow-hidden">
            <div
              className="h-2 rounded-full transition-all duration-1000"
              style={{ width: `${pct}%`, background: cfg.color }}
            />
          </div>
          {estado && (
            <p className="text-xs mt-1.5 font-medium" style={{ color: cfg.color }}>
              {estado.mensaje || "Procesando..."}
            </p>
          )}
        </div>
      )}

      {/* Detalle expandido */}
      {expanded && (item.estado === "EJECUTANDO" || item.estado === "COMPLETADO") && estado && (
        <div className="px-4 pb-4 pt-1 border-t border-white/40">
          <div className="grid grid-cols-3 gap-3 mt-2">
            {[
              { label: "Conciliados",  value: (estado.conciliados ?? 0).toLocaleString(), color: "#10b981" },
              { label: "Pendientes",   value: (estado.pendientes  ?? 0).toLocaleString(), color: "#f59e0b" },
              { label: "Efectividad",  value: `${(estado.tasa ?? 0).toFixed(1)}%`,        color: "#667eea" },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-white/70 rounded-xl p-3 text-center">
                <div className="text-lg font-bold" style={{ color }}>{value}</div>
                <div className="text-[10px] text-[#64748b] uppercase tracking-wide mt-0.5">{label}</div>
              </div>
            ))}
          </div>
          {item.estado === "COMPLETADO" && (
            <div className="mt-3 flex items-center gap-2 text-xs text-[#10b981] font-medium">
              <CheckCircle className="w-3.5 h-3.5" />
              Conciliación completada exitosamente
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────
export default function ScheduledProgress() {
  const { scheduled, cancelScheduled, refreshHistorial } = useReconciliation();
  const [estado, setEstado] = useState<EstadoBackend | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  // Polling del estado del proceso cuando hay algo ejecutando
  const hayEjecutando = scheduled.some(s => s.estado === "EJECUTANDO");

  const fetchEstado = useCallback(async () => {
    try {
      const { data } = await axios.get("/api/estado/", { timeout: 5_000 });
      setEstado(data);
      // Si terminó, refrescar el historial
      if (data.fase === "listo" || data.fase === "error") {
        await refreshHistorial();
      }
    } catch { /* backend no disponible */ }
  }, [refreshHistorial]);

  useEffect(() => {
    if (!hayEjecutando) return;
    fetchEstado();
    const id = setInterval(fetchEstado, 3_000);
    return () => clearInterval(id);
  }, [hayEjecutando, fetchEstado]);

  // Solo mostrar si hay programadas relevantes
  const visibles = scheduled.filter(s =>
    s.estado === "PENDIENTE" || s.estado === "EJECUTANDO" ||
    s.estado === "COMPLETADO" || s.estado === "ERROR"
  );

  if (visibles.length === 0) return null;

  const ejecutando = visibles.filter(s => s.estado === "EJECUTANDO");
  const pendientes = visibles.filter(s => s.estado === "PENDIENTE");
  const completadas = visibles.filter(s => s.estado === "COMPLETADO" || s.estado === "ERROR");

  return (
    <div className="bg-white rounded-[20px] overflow-hidden"
         style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.06)" }}>

      {/* Header */}
      <button
        onClick={() => setCollapsed(v => !v)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-[#f8fafc] transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center"
               style={{ background: "linear-gradient(135deg, #667eea, #764ba2)" }}>
            <CalendarClock className="w-4 h-4 text-white" />
          </div>
          <div className="text-left">
            <p className="text-sm font-bold text-[#1e293b]">Ejecuciones Programadas</p>
            <p className="text-xs text-[#64748b]">
              {ejecutando.length > 0 && `${ejecutando.length} ejecutando · `}
              {pendientes.length > 0 && `${pendientes.length} pendiente${pendientes.length > 1 ? "s" : ""} · `}
              {completadas.length > 0 && `${completadas.length} completada${completadas.length > 1 ? "s" : ""}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {ejecutando.length > 0 && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-600 border border-amber-200">
              <Loader2 className="w-3 h-3 animate-spin" /> En proceso
            </span>
          )}
          {collapsed ? <ChevronDown className="w-4 h-4 text-[#94a3b8]" /> : <ChevronUp className="w-4 h-4 text-[#94a3b8]" />}
        </div>
      </button>

      {/* Lista */}
      {!collapsed && (
        <div className="px-5 pb-5 space-y-3 border-t border-[#f1f5f9]">
          <div className="pt-4 space-y-3">
            {/* Ejecutando primero */}
            {ejecutando.map(item => (
              <ScheduledRow
                key={item.id}
                item={item}
                estado={estado}
                onCancel={cancelScheduled}
                onRefresh={refreshHistorial}
              />
            ))}
            {/* Pendientes */}
            {pendientes.map(item => (
              <ScheduledRow
                key={item.id}
                item={item}
                estado={null}
                onCancel={cancelScheduled}
                onRefresh={refreshHistorial}
              />
            ))}
            {/* Completadas/Error (últimas 3) */}
            {completadas.slice(0, 3).map(item => (
              <ScheduledRow
                key={item.id}
                item={item}
                estado={item.estado === "COMPLETADO" ? estado : null}
                onCancel={cancelScheduled}
                onRefresh={refreshHistorial}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
