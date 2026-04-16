import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  CalendarClock,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  Trash2,
  ChevronDown,
  ChevronUp,
  Timer,
  RefreshCw,
  FileSpreadsheet,
  AlertTriangle,
} from "lucide-react";
import { useReconciliation } from "@/context/ReconciliationContext";

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
  if (!msg || m.includes("subiendo")) return 5;
  if (m.includes("leyendo") || m.includes("filtrando")) return 10;
  if (m.includes("insertando")) return 18;
  if (m.includes("f1-f4") && m.includes("[")) {
    const match = m.match(/\[(\d+)\/(\d+)\]/);
    if (match)
      return Math.round(22 + (parseInt(match[1]) / parseInt(match[2])) * 38);
    return 30;
  }
  if (m.includes("f1-f4")) return 22;
  if (m.includes("f6") || m.includes("subset")) return 65;
  if (m.includes("f5") || m.includes("monto puro")) return 80;
  if (m.includes("generando reporte")) return 90;
  if (m.includes("procesando")) return 15;
  return 50;
}

const ESTADO_CFG = {
  PENDIENTE: {
    color: "#667eea",
    bg: "rgba(102,126,234,0.07)",
    label: "Pendiente",
    Icon: Clock,
  },
  EJECUTANDO: {
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.07)",
    label: "Ejecutando",
    Icon: Loader2,
  },
  COMPLETADO: {
    color: "#10b981",
    bg: "rgba(16,185,129,0.07)",
    label: "Completado",
    Icon: CheckCircle,
  },
  ERROR: {
    color: "#ef4444",
    bg: "rgba(239,68,68,0.07)",
    label: "Error",
    Icon: XCircle,
  },
  CANCELADO: {
    color: "#94a3b8",
    bg: "rgba(148,163,184,0.07)",
    label: "Cancelado",
    Icon: XCircle,
  },
} as const;

// ── Fila individual ───────────────────────────────────────────────────────────
function ProgramadaRow({
  item,
  estadoBackend,
  onCancel,
}: {
  item: any;
  estadoBackend: any;
  onCancel: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(item.estado === "EJECUTANDO");
  const [countdown, setCountdown] = useState(() => {
    const dt = new Date(`${item.fecha}T${item.hora}:00`);
    return Math.max(0, Math.floor((dt.getTime() - Date.now()) / 1000));
  });

  useEffect(() => {
    if (item.estado !== "PENDIENTE" || countdown <= 0) return;
    const id = setInterval(() => setCountdown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [item.estado, countdown]);

  const cfg =
    ESTADO_CFG[item.estado as keyof typeof ESTADO_CFG] ?? ESTADO_CFG.PENDIENTE;
  const { Icon } = cfg;
  const pct =
    item.estado === "EJECUTANDO" && estadoBackend
      ? getProgressPct(estadoBackend.mensaje ?? "")
      : item.estado === "COMPLETADO"
        ? 100
        : 0;

  return (
    <div
      className="rounded-2xl border overflow-hidden transition-all"
      style={{ borderColor: cfg.color + "35", background: cfg.bg }}
    >
      {/* Cabecera de la fila */}
      <div className="flex items-center gap-3 p-5">
        {/* Icono */}
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: cfg.color + "18" }}
        >
          <Icon
            className={`w-5 h-5 ${item.estado === "EJECUTANDO" ? "animate-spin" : ""}`}
            style={{ color: cfg.color }}
          />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-sm font-bold text-[#1e293b] truncate">
              {item.archivo}
            </span>
            <span
              className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide"
              style={{ background: cfg.color + "18", color: cfg.color }}
            >
              {cfg.label}
            </span>
            {item.estado === "PENDIENTE" && (
              <span
                className="flex items-center gap-1 text-xs font-mono font-semibold"
                style={{ color: countdown <= 0 ? "#f59e0b" : "#667eea" }}
              >
                <Timer className="w-3 h-3" />
                {countdown <= 0 ? "Iniciando..." : formatCountdown(countdown)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-4 text-xs text-[#64748b] flex-wrap">
            <span>
              <CalendarClock className="w-3 h-3 inline mr-1 opacity-60" />
              {item.fecha} ·{" "}
              <strong className="text-[#1e293b]">{item.hora}</strong>
            </span>
            {item.ejecutado_en && <span>Ejecutado: {item.ejecutado_en}</span>}
            <span className="opacity-50">Creado: {item.creado_en}</span>
          </div>
        </div>

        {/* Acciones */}
        <div className="flex items-center gap-1.5 shrink-0">
          {item.estado === "PENDIENTE" && (
            <button
              onClick={() => onCancel(item.id)}
              title="Cancelar"
              className="p-2 rounded-xl hover:bg-red-50 text-[#94a3b8] hover:text-red-500 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
          {(item.estado === "EJECUTANDO" ||
            item.estado === "COMPLETADO" ||
            item.estado === "ERROR") && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="p-2 rounded-xl hover:bg-white/60 text-[#94a3b8] transition-colors"
            >
              {expanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Barra de progreso */}
      {(item.estado === "EJECUTANDO" || item.estado === "COMPLETADO") && (
        <div className="px-5 pb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium" style={{ color: cfg.color }}>
              {item.estado === "COMPLETADO"
                ? "Completado"
                : estadoBackend?.mensaje || "Procesando..."}
            </span>
            <span
              className="text-xs font-mono font-bold"
              style={{ color: cfg.color }}
            >
              {pct}%
            </span>
          </div>
          <div className="w-full bg-white/60 rounded-full h-2.5 overflow-hidden">
            <div
              className="h-2.5 rounded-full transition-all duration-1000"
              style={{ width: `${pct}%`, background: cfg.color }}
            />
          </div>
        </div>
      )}

      {/* Detalle expandido */}
      {expanded &&
        estadoBackend &&
        (item.estado === "EJECUTANDO" || item.estado === "COMPLETADO") && (
          <div className="px-5 pb-5 pt-1 border-t border-white/40 space-y-4">
            <div className="grid grid-cols-3 gap-3">
              {[
                {
                  label: "Conciliados",
                  value: (estadoBackend.conciliados ?? 0).toLocaleString(),
                  color: "#10b981",
                },
                {
                  label: "Pendientes",
                  value: (estadoBackend.pendientes ?? 0).toLocaleString(),
                  color: "#f59e0b",
                },
                {
                  label: "Efectividad",
                  value: `${(estadoBackend.tasa ?? 0).toFixed(1)}%`,
                  color: "#667eea",
                },
              ].map(({ label, value, color }) => (
                <div
                  key={label}
                  className="bg-white/70 rounded-xl p-3 text-center"
                >
                  <div className="text-xl font-bold" style={{ color }}>
                    {value}
                  </div>
                  <div className="text-[10px] text-[#64748b] uppercase tracking-wide mt-0.5">
                    {label}
                  </div>
                </div>
              ))}
            </div>
            {item.estado === "COMPLETADO" && (
              <p className="text-xs text-[#10b981] font-semibold flex items-center gap-1.5">
                <CheckCircle className="w-3.5 h-3.5" /> Conciliación completada
                exitosamente
              </p>
            )}
          </div>
        )}

      {/* Error detail */}
      {expanded && item.estado === "ERROR" && (
        <div className="px-5 pb-5 pt-1 border-t border-white/40">
          <p className="text-xs text-red-500 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            La ejecución falló. Revisa los logs del servidor para más detalles.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Sección principal ─────────────────────────────────────────────────────────
export default function ProgramadasSection() {
  const { scheduled, cancelScheduled, refreshHistorial } = useReconciliation();
  const [estadoBackend, setEstadoBackend] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);

  const hayEjecutando = scheduled.some((s) => s.estado === "EJECUTANDO");

  // Polling del estado cuando hay algo ejecutando
  const fetchEstado = useCallback(async () => {
    try {
      const { data } = await axios.get("/api/estado/", { timeout: 5_000 });
      setEstadoBackend(data);
      if (data.fase === "listo" || data.fase === "error") {
        await refreshHistorial();
      }
    } catch {
      /* backend no disponible */
    }
  }, [refreshHistorial]);

  useEffect(() => {
    if (!hayEjecutando) return;
    fetchEstado();
    const id = setInterval(fetchEstado, 3_000);
    return () => clearInterval(id);
  }, [hayEjecutando, fetchEstado]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshHistorial();
    setRefreshing(false);
  };

  // Ordenar: ejecutando → pendientes → completadas/error → canceladas
  const ORDER = {
    EJECUTANDO: 0,
    PENDIENTE: 1,
    COMPLETADO: 2,
    ERROR: 3,
    CANCELADO: 4,
  };
  const sorted = [...scheduled].sort(
    (a, b) =>
      (ORDER[a.estado as keyof typeof ORDER] ?? 5) -
      (ORDER[b.estado as keyof typeof ORDER] ?? 5),
  );

  const counts = {
    ejecutando: scheduled.filter((s) => s.estado === "EJECUTANDO").length,
    pendientes: scheduled.filter((s) => s.estado === "PENDIENTE").length,
    completadas: scheduled.filter((s) => s.estado === "COMPLETADO").length,
    errores: scheduled.filter((s) => s.estado === "ERROR").length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div
        className="bg-white rounded-[20px] p-6"
        style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.04)" }}
      >
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{
                background: "linear-gradient(135deg, #667eea, #764ba2)",
              }}
            >
              <CalendarClock className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-[#1e293b]">
                Ejecuciones Programadas
              </h2>
              <p className="text-xs text-[#64748b]">
                Monitor en tiempo real de conciliaciones automáticas
              </p>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs bg-[#f1f5f9] text-[#667eea] hover:bg-[#e0e7ff] transition-colors font-medium"
          >
            <RefreshCw
              className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`}
            />
            Actualizar
          </button>
        </div>

        {/* KPIs de estado */}
        <div className="grid grid-cols-4 gap-3">
          {[
            {
              label: "Ejecutando",
              value: counts.ejecutando,
              color: "#f59e0b",
              bg: "rgba(245,158,11,0.08)",
            },
            {
              label: "Pendientes",
              value: counts.pendientes,
              color: "#667eea",
              bg: "rgba(102,126,234,0.08)",
            },
            {
              label: "Completadas",
              value: counts.completadas,
              color: "#10b981",
              bg: "rgba(16,185,129,0.08)",
            },
            {
              label: "Errores",
              value: counts.errores,
              color: "#ef4444",
              bg: "rgba(239,68,68,0.08)",
            },
          ].map(({ label, value, color, bg }) => (
            <div
              key={label}
              className="rounded-2xl p-4 text-center"
              style={{ background: bg }}
            >
              <div className="text-2xl font-bold" style={{ color }}>
                {value}
              </div>
              <div className="text-[11px] text-[#64748b] uppercase tracking-wide mt-0.5">
                {label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Lista vacía */}
      {sorted.length === 0 && (
        <div
          className="bg-white rounded-[20px] p-12 text-center"
          style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.04)" }}
        >
          <FileSpreadsheet className="w-14 h-14 mx-auto mb-4 text-[#cbd5e1]" />
          <h3 className="text-base font-bold text-[#1e293b] mb-2">
            Sin ejecuciones programadas
          </h3>
          <p className="text-sm text-[#64748b]">
            Ve a <strong>Ejecutar Conciliación</strong> y usa el botón{" "}
            <strong>"Programar para nocturno"</strong> para agendar una
            ejecución automática.
          </p>
        </div>
      )}

      {/* Filas */}
      {sorted.length > 0 && (
        <div className="space-y-3">
          {sorted.map((item) => (
            <ProgramadaRow
              key={item.id}
              item={item}
              estadoBackend={
                item.estado === "EJECUTANDO" || item.estado === "COMPLETADO"
                  ? estadoBackend
                  : null
              }
              onCancel={cancelScheduled}
            />
          ))}
        </div>
      )}
    </div>
  );
}
