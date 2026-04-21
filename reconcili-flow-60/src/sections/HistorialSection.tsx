import { useState, useEffect } from "react";
import {
  useReconciliation,
  HistoryEntry,
} from "@/context/ReconciliationContext";
import { useApp, getMonthName } from "@/context/AppContext";
import {
  FileSpreadsheet,
  Eye,
  EyeOff,
  ChevronDown,
  RefreshCw,
  Filter,
  Calendar,
  Database,
  CalendarClock,
  Trash2,
  Timer,
  CheckCircle2,
  AlertTriangle,
  Ban,
} from "lucide-react";
import { ExcelIcon, PdfIcon } from "@/components/FileIcons";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from "recharts";
import StatCard from "@/components/StatCard";
import TransaccionesTable from "@/components/TransaccionesTable";
import { CheckCircle, Clock, Layers } from "lucide-react";

// ── Badge de estado con icono ─────────────────────────────────────────────────
function EstadoBadge({ estado }: { estado?: string }) {
  switch (estado) {
    case "CANCELADO":
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-600 border border-red-200">
          <Ban className="w-3 h-3" /> Cancelado
        </span>
      );
    case "ERROR":
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200">
          <AlertTriangle className="w-3 h-3" /> Error
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3" /> Completado
        </span>
      );
  }
}

// ── Color de fondo por estado ─────────────────────────────────────────────────
function rowBg(estado?: string) {
  if (estado === "CANCELADO") return "bg-red-50/70 border-l-4 border-l-red-400";
  if (estado === "ERROR") return "bg-amber-50/70 border-l-4 border-l-amber-400";
  return "bg-muted/50";
}

// ── Formatea segundos como "2h 15m 30s" ──────────────────────────────────────
function formatCountdown(secs: number): string {
  if (secs <= 0) return "Ejecutando...";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

// ── Cuenta regresiva en tiempo real ──────────────────────────────────────────
function Countdown({
  targetDate,
  targetTime,
}: {
  targetDate: string;
  targetTime: string;
}) {
  const [secs, setSecs] = useState<number>(() => {
    const dt = new Date(`${targetDate}T${targetTime}:00`);
    return Math.max(0, Math.floor((dt.getTime() - Date.now()) / 1000));
  });

  useEffect(() => {
    if (secs <= 0) return;
    const id = setInterval(() => setSecs((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [secs]);

  const isPast = secs <= 0;

  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-mono font-semibold ${
        isPast ? "text-warning" : "text-primary"
      }`}
    >
      <Timer className="w-3 h-3" />
      {isPast ? "Ejecutando en breve..." : formatCountdown(secs)}
    </span>
  );
}

export default function HistorialSection() {
  const {
    history,
    downloadReport,
    downloadReportPdf,
    refreshHistorial,
    getHistoryByMonth,
    scheduled,
    cancelScheduled,
  } = useReconciliation();
  const { currentMonthIndex, currentYear } = useApp();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [vistaDetalle, setVistaDetalle] = useState<{
    estado: "CONCILIADO" | "PENDIENTE";
    cuenta: string;
  } | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [mostrarTodo, setMostrarTodo] = useState(false);

  const mesLabel = `${getMonthName(currentMonthIndex)} ${currentYear}`;
  const historialMes = getHistoryByMonth(currentMonthIndex, currentYear);
  const historialFiltrado: HistoryEntry[] = mostrarTodo
    ? history
    : historialMes;
  const programadasPendientes = scheduled.filter(
    (s) => s.estado === "PENDIENTE" || s.estado === "EJECUTANDO",
  );

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshHistorial();
    setRefreshing(false);
  };

  if (history.length === 0) {
    return (
      <div className="bg-card rounded-2xl p-12 shadow-card text-center">
        <FileSpreadsheet className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-card-foreground mb-2">
          Sin historial
        </h3>
        <p className="text-muted-foreground text-sm mb-4">
          Las ejecuciones de conciliación aparecerán aquí automáticamente.
        </p>
        <button
          onClick={handleRefresh}
          className="px-3 py-1.5 rounded-full text-xs bg-primary/10 text-primary hover:bg-primary/20 transition-colors inline-flex items-center gap-1.5"
        >
          <RefreshCw
            className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`}
          />{" "}
          Actualizar
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-card rounded-2xl p-6 shadow-card">
        {/* Tabla de detalle — reemplaza la vista al abrirse */}
        {vistaDetalle && (
          <TransaccionesTable
            estado={vistaDetalle.estado}
            cuenta={vistaDetalle.cuenta}
            onClose={() => setVistaDetalle(null)}
          />
        )}

        {!vistaDetalle && (
          <>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2 flex-wrap">
                <Calendar className="w-4 h-4 text-primary" />
                <h3 className="text-base font-semibold text-card-foreground">
                  {mostrarTodo
                    ? `Todo el historial (${history.length} ejecuciones)`
                    : `${mesLabel} — ${historialMes.length} ejecución${historialMes.length !== 1 ? "es" : ""}`}
                </h3>
                {/* Badges de estado */}
                {(() => {
                  const src = mostrarTodo ? history : historialMes;
                  const completadas = src.filter(
                    (h) => !h.estado || h.estado === "COMPLETADO",
                  ).length;
                  const canceladas = src.filter(
                    (h) => h.estado === "CANCELADO",
                  ).length;
                  const errores = src.filter(
                    (h) => h.estado === "ERROR",
                  ).length;
                  return (
                    <>
                      {completadas > 0 && (
                        <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-success/10 text-success">
                          {completadas} completada{completadas !== 1 ? "s" : ""}
                        </span>
                      )}
                      {canceladas > 0 && (
                        <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-100 text-red-600">
                          {canceladas} cancelada{canceladas !== 1 ? "s" : ""}
                        </span>
                      )}
                      {errores > 0 && (
                        <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-600">
                          {errores} con error
                        </span>
                      )}
                    </>
                  );
                })()}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setMostrarTodo((v) => !v);
                    setSelectedId(null);
                  }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border transition-colors ${
                    mostrarTodo
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border hover:border-primary text-muted-foreground hover:text-primary"
                  }`}
                >
                  <Filter className="w-3 h-3" />
                  {mostrarTodo ? "Ver solo este mes" : "Ver todo el historial"}
                </button>
                <button
                  onClick={handleRefresh}
                  className="px-3 py-1.5 rounded-full text-xs bg-primary/10 text-primary hover:bg-primary/20 transition-colors flex items-center gap-1.5"
                >
                  <RefreshCw
                    className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`}
                  />{" "}
                  Actualizar
                </button>
              </div>
            </div>

            {/* Sin datos para el mes seleccionado */}
            {!mostrarTodo && historialMes.length === 0 && (
              <div className="bg-muted/50 rounded-2xl p-6 text-center">
                <p className="text-muted-foreground text-sm">
                  No hay ejecuciones registradas para{" "}
                  <strong className="text-card-foreground">{mesLabel}</strong>.
                </p>
                <button
                  onClick={() => setMostrarTodo(true)}
                  className="mt-3 text-xs text-primary hover:underline"
                >
                  Ver todo el historial ({history.length} ejecuciones) →
                </button>
              </div>
            )}

            {/* Programadas pendientes (mini-lista dentro del card) */}
            {programadasPendientes.length > 0 && (
              <div className="mb-6 space-y-2">
                <p className="text-xs text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <CalendarClock className="w-3.5 h-3.5 text-primary" />{" "}
                  Programadas
                </p>
                {programadasPendientes.map((p) => {
                  const isPast =
                    new Date(`${p.fecha}T${p.hora}:00`) <= new Date();
                  return (
                    <div
                      key={p.id}
                      className={`flex items-center p-4 rounded-2xl border transition-colors ${
                        p.estado === "EJECUTANDO"
                          ? "bg-warning/5 border-warning/30"
                          : isPast
                            ? "bg-primary/5 border-primary/20 animate-pulse"
                            : "bg-primary/5 border-primary/20"
                      }`}
                    >
                      <CalendarClock
                        className={`w-5 h-5 mr-3 shrink-0 ${p.estado === "EJECUTANDO" ? "text-warning" : "text-primary"}`}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium text-card-foreground truncate">
                            {p.archivo}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                              p.estado === "EJECUTANDO"
                                ? "bg-warning/10 text-warning"
                                : isPast
                                  ? "bg-primary/10 text-primary"
                                  : "bg-muted text-muted-foreground"
                            }`}
                          >
                            {p.estado === "EJECUTANDO"
                              ? "⚙ Ejecutando..."
                              : isPast
                                ? "⏰ Iniciando..."
                                : "📅 Programado"}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 mt-1 flex-wrap">
                          <span className="text-xs text-muted-foreground">
                            {p.fecha} a las{" "}
                            <strong className="text-card-foreground">
                              {p.hora}
                            </strong>
                          </span>
                          {p.estado === "PENDIENTE" && (
                            <Countdown
                              targetDate={p.fecha}
                              targetTime={p.hora}
                            />
                          )}
                        </div>
                      </div>
                      {p.estado === "PENDIENTE" && (
                        <button
                          onClick={() => cancelScheduled(p.id)}
                          className="ml-3 p-1.5 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Lista de ejecuciones completadas */}
            {historialFiltrado.length > 0 && (
              <div className="space-y-2">
                {historialFiltrado.map((item) => {
                  const rowKey = item.id ?? item.date + item.cuenta;
                  const isSelected = selectedId === (item.id ?? null);
                  const total = item.total ?? 0;
                  const tasa =
                    item.tasa ??
                    (total > 0 ? ((item.conciliados ?? 0) / total) * 100 : 0);
                  const barData = [
                    {
                      name: "Total",
                      valor: total,
                      fill: "hsl(var(--primary))",
                    },
                    {
                      name: "Conciliados",
                      valor: item.conciliados ?? 0,
                      fill: "hsl(var(--success))",
                    },
                    {
                      name: "Pendientes",
                      valor: item.pendientes ?? 0,
                      fill: "hsl(var(--warning))",
                    },
                  ];

                  return (
                    <div key={String(rowKey)}>
                      <div
                        onClick={() =>
                          setSelectedId(isSelected ? null : (item.id ?? null))
                        }
                        className={`cursor-pointer flex items-center p-4 rounded-2xl hover:brightness-95 transition-all ${rowBg(item.estado)}`}
                      >
                        <div className="w-[130px] shrink-0">
                          <p className="text-xs text-muted-foreground">Fecha</p>
                          <p className="text-sm font-medium text-card-foreground">
                            {item.date}
                          </p>
                        </div>
                        <div className="flex-1 flex gap-5 flex-wrap">
                          <div className="flex flex-col gap-0.5">
                            <span className="text-[11px] text-muted-foreground uppercase">
                              Cuenta
                            </span>
                            <span className="text-sm font-semibold text-card-foreground">
                              {item.cuenta}
                            </span>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-[11px] text-muted-foreground uppercase">
                              Registros
                            </span>
                            <span className="text-sm font-semibold text-card-foreground">
                              {total.toLocaleString()}
                            </span>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-[11px] text-muted-foreground uppercase">
                              Conciliados
                            </span>
                            <span className="text-sm font-semibold text-card-foreground">
                              {(item.conciliados ?? 0).toLocaleString()} (
                              {item.efectividad})
                            </span>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-[11px] text-muted-foreground uppercase">
                              Pendientes
                            </span>
                            <span className="text-sm font-semibold text-card-foreground">
                              {(item.pendientes ?? 0).toLocaleString()}
                            </span>
                          </div>
                          {item.periodo && (
                            <div className="flex flex-col gap-0.5">
                              <span className="text-[11px] text-muted-foreground uppercase">
                                Período
                              </span>
                              <span className="text-sm font-semibold text-card-foreground">
                                {item.periodo}
                              </span>
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          <EstadoBadge estado={item.estado} />
                          <ChevronDown
                            className={`w-4 h-4 text-muted-foreground transition-transform ${isSelected ? "rotate-180" : ""}`}
                          />
                        </div>
                      </div>

                      {isSelected && (
                        <div className="mt-2 p-6 bg-background rounded-2xl border border-border space-y-6">
                          <div className="flex items-start justify-between gap-4">
                            <h4 className="text-sm font-semibold text-card-foreground">
                              Detalle — {item.date} — Cuenta {item.cuenta}
                              {item.id && (
                                <span className="ml-2 text-xs text-muted-foreground font-normal">
                                  (Ejecución #{item.id})
                                </span>
                              )}
                            </h4>
                            <EstadoBadge estado={item.estado} />
                          </div>

                          {/* Banner de estado no completado */}
                          {item.estado === "ERROR" && (
                            <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-50 border border-amber-200">
                              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                              <div>
                                <p className="text-sm font-semibold text-amber-800">La ejecución falló</p>
                                <p className="text-xs text-amber-700 mt-0.5">
                                  Revisa los logs del servidor para ver el error detallado. Los datos parcialmente procesados quedaron registrados.
                                </p>
                              </div>
                            </div>
                          )}
                          {item.estado === "CANCELADO" && (
                            <div className="flex items-start gap-3 p-4 rounded-xl bg-red-50 border border-red-200">
                              <Ban className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                              <div>
                                <p className="text-sm font-semibold text-red-800">Ejecución cancelada por el usuario</p>
                                <p className="text-xs text-red-700 mt-0.5">
                                  Se procesaron {(item.conciliados ?? 0).toLocaleString()} registros antes de la cancelación.
                                </p>
                              </div>
                            </div>
                          )}
                          <div className="h-48">
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={barData} barSize={40}>
                                <CartesianGrid
                                  strokeDasharray="3 3"
                                  stroke="hsl(var(--border))"
                                />
                                <XAxis
                                  dataKey="name"
                                  tick={{
                                    fontSize: 11,
                                    fill: "hsl(var(--muted-foreground))",
                                  }}
                                />
                                <YAxis
                                  tickFormatter={(v: number) =>
                                    v >= 1000
                                      ? `${(v / 1000).toFixed(0)}k`
                                      : String(v)
                                  }
                                  tick={{
                                    fontSize: 11,
                                    fill: "hsl(var(--muted-foreground))",
                                  }}
                                />
                                <Tooltip
                                  formatter={(value: number) =>
                                    (value ?? 0).toLocaleString()
                                  }
                                  contentStyle={{
                                    background: "hsl(var(--card))",
                                    border: "1px solid hsl(var(--border))",
                                    borderRadius: "12px",
                                    fontSize: "13px",
                                  }}
                                />
                                <Bar dataKey="valor" radius={[6, 6, 0, 0]}>
                                  {barData.map((entry, idx) => (
                                    <Cell key={idx} fill={entry.fill} />
                                  ))}
                                </Bar>
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
                            <StatCard
                              title="Total"
                              value={total.toLocaleString()}
                              icon={Database}
                            />
                            <StatCard
                              title="Conciliados"
                              value={(item.conciliados ?? 0).toLocaleString()}
                              icon={CheckCircle}
                            />
                            <StatCard
                              title="Pendientes"
                              value={(item.pendientes ?? 0).toLocaleString()}
                              icon={Clock}
                            />
                            <StatCard
                              title="Efectividad"
                              value={`${tasa.toFixed(1)}%`}
                              icon={Layers}
                            />
                          </div>
                          <div className="flex gap-3 flex-wrap">
                            <button
                              onClick={() =>
                                setVistaDetalle({
                                  estado: "CONCILIADO",
                                  cuenta: item.cuenta,
                                })
                              }
                              className="bg-success/10 text-success px-4 py-2 rounded-full text-sm font-medium inline-flex items-center gap-2 hover:bg-success/20 transition-colors"
                            >
                              <Eye className="w-4 h-4" /> Ver Conciliados (
                              {(item.conciliados ?? 0).toLocaleString()})
                            </button>
                            <button
                              onClick={() =>
                                setVistaDetalle({
                                  estado: "PENDIENTE",
                                  cuenta: item.cuenta,
                                })
                              }
                              className="bg-warning/10 text-warning px-4 py-2 rounded-full text-sm font-medium inline-flex items-center gap-2 hover:bg-warning/20 transition-colors"
                            >
                              <EyeOff className="w-4 h-4" /> Ver Pendientes (
                              {(item.pendientes ?? 0).toLocaleString()})
                            </button>
                            {item.ruta_reporte && (
                              <button
                                onClick={() =>
                                  downloadReport(item.ruta_reporte)
                                }
                                className="gradient-primary text-primary-foreground px-5 py-2 rounded-full text-sm font-medium inline-flex items-center gap-2 shadow-lg hover:-translate-y-0.5 transition-all"
                              >
                                <ExcelIcon className="w-4 h-4" /> Descargar
                                Excel
                              </button>
                            )}
                            {item.ruta_reporte && (
                              <button
                                onClick={() =>
                                  downloadReportPdf(item.ruta_reporte)
                                }
                                className="bg-red-600 text-white px-5 py-2 rounded-full text-sm font-medium inline-flex items-center gap-2 shadow-lg hover:bg-red-700 hover:-translate-y-0.5 transition-all"
                              >
                                <PdfIcon className="w-4 h-4" /> Descargar PDF
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
