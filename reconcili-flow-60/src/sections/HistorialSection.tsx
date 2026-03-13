import { useState } from "react";
import { useReconciliation, HistoryEntry } from "@/context/ReconciliationContext";
import { useApp, getMonthName } from "@/context/AppContext";
import { Download, FileSpreadsheet, Eye, EyeOff, ChevronDown, RefreshCw, Filter, Calendar } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer } from "recharts";
import StatCard from "@/components/StatCard";
import TransaccionesTable from "@/components/TransaccionesTable";
import { CheckCircle, Clock, Database, Layers } from "lucide-react";

export default function HistorialSection() {
  const { history, downloadReport, refreshHistorial, getHistoryByMonth } = useReconciliation();
  const { currentMonthIndex, currentYear } = useApp();
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [vistaDetalle, setVistaDetalle] = useState<{ estado: "CONCILIADO" | "PENDIENTE"; cuenta: string } | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [mostrarTodo, setMostrarTodo] = useState(false);

  const mesLabel = `${getMonthName(currentMonthIndex)} ${currentYear}`;
  const historialMes = getHistoryByMonth(currentMonthIndex, currentYear);
  const historialFiltrado = mostrarTodo ? history : historialMes;
  const hayDatosEnMes = historialMes.length > 0;

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshHistorial();
    setRefreshing(false);
  };

  if (history.length === 0) {
    return (
      <div className="bg-card rounded-2xl p-12 shadow-card text-center">
        <FileSpreadsheet className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-card-foreground mb-2">Sin historial</h3>
        <p className="text-muted-foreground text-sm mb-4">
          Las ejecuciones de conciliación aparecerán aquí automáticamente.
        </p>
        <button
          onClick={handleRefresh}
          className="px-3 py-1.5 rounded-full text-xs bg-primary/10 text-primary hover:bg-primary/20 transition-colors inline-flex items-center gap-1.5"
        >
          <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} /> Actualizar
        </button>
      </div>
    );
  }

  if (vistaDetalle) {
    return (
      <TransaccionesTable
        estado={vistaDetalle.estado}
        cuenta={vistaDetalle.cuenta}
        onClose={() => setVistaDetalle(null)}
      />
    );
  }

  return (
    <div className="bg-card rounded-2xl p-6 shadow-card">
      {/* Header con filtro */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-primary" />
          <h3 className="text-base font-semibold text-card-foreground">
            {mostrarTodo
              ? `Todo el historial (${history.length} ejecuciones)`
              : `${mesLabel} (${historialMes.length} ejecuciones)`
            }
          </h3>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => { setMostrarTodo(v => !v); setSelectedIndex(null); }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-border hover:border-primary text-muted-foreground hover:text-primary transition-colors"
          >
            <Filter className="w-3 h-3" />
            {mostrarTodo ? "Ver solo este mes" : "Ver todo el historial"}
          </button>
          <button
            onClick={handleRefresh}
            className="px-3 py-1.5 rounded-full text-xs bg-primary/10 text-primary hover:bg-primary/20 transition-colors flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} /> Actualizar
          </button>
        </div>
      </div>

      {/* Sin datos para el mes */}
      {!mostrarTodo && !hayDatosEnMes && (
        <div className="bg-muted/50 rounded-2xl p-6 text-center">
          <p className="text-muted-foreground text-sm">
            No hay conciliaciones registradas para <strong className="text-card-foreground">{mesLabel}</strong>.
          </p>
          <button onClick={() => setMostrarTodo(true)} className="mt-3 text-xs text-primary hover:underline">
            Ver todo el historial →
          </button>
        </div>
      )}

      {/* Lista */}
      {historialFiltrado.length > 0 && (
        <div className="space-y-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">
            {mostrarTodo
              ? `Historial completo (${history.length})`
              : `Conciliaciones de ${mesLabel} (${historialMes.length})`}
          </p>

          <div className="space-y-2">
            {historialFiltrado.map((item, i) => {
              const isSelected = selectedIndex === i;
              const total = item.total ?? 0;
              const tasa = item.tasa ?? (total > 0 ? ((item.conciliados ?? 0) / total) * 100 : 0);
              const barData = [
                { name: "Total", valor: total, fill: "hsl(var(--primary))" },
                { name: "Conciliados", valor: item.conciliados ?? 0, fill: "hsl(var(--success))" },
                { name: "Pendientes", valor: item.pendientes ?? 0, fill: "hsl(var(--warning))" },
              ];
              return (
                <div key={i}>
                  <div
                    onClick={() => setSelectedIndex(isSelected ? null : i)}
                    className="cursor-pointer flex items-center p-4 bg-muted/50 rounded-2xl hover:bg-muted transition-colors"
                  >
                    <div className="w-[110px] font-medium text-card-foreground text-sm">{item.date}</div>
                    <div className="flex-1 flex gap-6">
                      <div className="flex flex-col gap-1">
                        <span className="text-[11px] text-muted-foreground uppercase">Cuenta</span>
                        <span className="text-sm font-semibold text-card-foreground">{item.cuenta}</span>
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-[11px] text-muted-foreground uppercase">Registros</span>
                        <span className="text-sm font-semibold text-card-foreground">{total.toLocaleString()}</span>
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-[11px] text-muted-foreground uppercase">Conciliados</span>
                        <span className="text-sm font-semibold text-card-foreground">{(item.conciliados ?? 0).toLocaleString()} ({item.efectividad})</span>
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-[11px] text-muted-foreground uppercase">Pendientes</span>
                        <span className="text-sm font-semibold text-card-foreground">{(item.pendientes ?? 0).toLocaleString()}</span>
                      </div>
                      {item.periodo && (
                        <div className="flex flex-col gap-1">
                          <span className="text-[11px] text-muted-foreground uppercase">Período</span>
                          <span className="text-sm font-semibold text-card-foreground">{item.periodo}</span>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="px-3 py-1 rounded-full text-xs font-medium bg-success/10 text-success">
                        Completado
                      </span>
                      <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${isSelected ? "rotate-180" : ""}`} />
                    </div>
                  </div>

                  {isSelected && (
                    <div className="mt-2 p-6 bg-background rounded-2xl border border-border space-y-6">
                      <h4 className="text-sm font-semibold text-card-foreground">
                        Detalle — {item.date} — Cuenta {item.cuenta}
                      </h4>

                      <div className="h-48">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={barData} barSize={40}>
                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                            <XAxis dataKey="name" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                            <YAxis
                              tickFormatter={(v: number) => (v >= 1000 ? (v / 1000).toFixed(0) + "k" : String(v))}
                              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                            />
                            <Tooltip
                              formatter={(value: number) => (value ?? 0).toLocaleString()}
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
                        <StatCard title="Total" value={total.toLocaleString()} icon={Database} />
                        <StatCard title="Conciliados" value={(item.conciliados ?? 0).toLocaleString()} icon={CheckCircle} />
                        <StatCard title="Pendientes" value={(item.pendientes ?? 0).toLocaleString()} icon={Clock} />
                        <StatCard title="Efectividad" value={`${tasa.toFixed(1)}%`} icon={Layers} />
                      </div>

                      <div className="flex gap-3 flex-wrap">
                        <button
                          onClick={() => setVistaDetalle({ estado: "CONCILIADO", cuenta: item.cuenta })}
                          className="bg-success/10 text-success px-4 py-2 rounded-full text-sm font-medium inline-flex items-center gap-2 hover:bg-success/20 transition-colors"
                        >
                          <Eye className="w-4 h-4" /> Ver Conciliados ({(item.conciliados ?? 0).toLocaleString()})
                        </button>
                        <button
                          onClick={() => setVistaDetalle({ estado: "PENDIENTE", cuenta: item.cuenta })}
                          className="bg-warning/10 text-warning px-4 py-2 rounded-full text-sm font-medium inline-flex items-center gap-2 hover:bg-warning/20 transition-colors"
                        >
                          <EyeOff className="w-4 h-4" /> Ver Pendientes ({(item.pendientes ?? 0).toLocaleString()})
                        </button>
                        {item.ruta_reporte && (
                          <button
                            onClick={() => downloadReport(item.ruta_reporte)}
                            className="gradient-primary text-primary-foreground px-5 py-2 rounded-full text-sm font-medium inline-flex items-center gap-2 shadow-lg hover:-translate-y-0.5 transition-all"
                          >
                            <Download className="w-4 h-4" /> Descargar Excel
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
