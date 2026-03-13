import { useState } from "react";
import { Database, CheckCircle, Clock as ClockIcon, Hourglass, Zap, Layers, Cpu, Moon, Play, Upload, Download, Loader2, FileSpreadsheet, Calendar, Eye, EyeOff } from "lucide-react";
import StatCard from "@/components/StatCard";
import PhaseBadge from "@/components/PhaseBadge";
import ChartSection from "@/components/ChartSection";
import ErrorAlert from "@/components/ErrorAlert";
import TransaccionesTable from "@/components/TransaccionesTable";
import { useApp, getMonthName } from "@/context/AppContext";
import { useReconciliation } from "@/context/ReconciliationContext";

export default function DashboardSection() {
  const { currentMonthIndex, currentYear, setActiveSection } = useApp();
  const { state, result, errorMessage, history, reset, downloadReport, getHistoryByMonth } = useReconciliation();

  const [vistaDetalle, setVistaDetalle] = useState<{ estado: "CONCILIADO" | "PENDIENTE"; cuenta: string } | null>(null);

  const historialMes = getHistoryByMonth(currentMonthIndex, currentYear);
  const ultimoDelMes = historialMes[0] ?? null;
  const esMesActual = result?.mes === currentMonthIndex && result?.anio === currentYear;
  const dataMes: any = esMesActual ? result : ultimoDelMes ?? result ?? history[0] ?? null;
  const esDatoDelMes = esMesActual || !!ultimoDelMes;

  const totalRegistros = dataMes?.total_leido ?? dataMes?.total ?? 0;
  const conciliados = dataMes?.conciliados ?? 0;
  const pendientes = dataMes?.pendientes ?? 0;
  const cuenta = dataMes?.cuenta_procesada ?? dataMes?.cuenta ?? "—";
  const tasa = dataMes?.tasa_conciliacion ?? dataMes?.tasa ?? 0;
  const efectividad = tasa > 0 ? tasa.toFixed(1) : totalRegistros > 0 ? ((conciliados / totalRegistros) * 100).toFixed(1) : "0";
  const hasData = totalRegistros > 0;
  const mesLabel = `${getMonthName(currentMonthIndex)} ${currentYear}`;

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
    <div className="space-y-8">
      {/* Phase badges */}
      <div className="flex gap-3 flex-wrap">
        <PhaseBadge phase="F0" label="F0: Normalización" icon={<Loader2 className="w-3.5 h-3.5" />} variant="f0" />
        <PhaseBadge phase="F1" label="F1: Fast-Pass" icon={<Zap className="w-3.5 h-3.5" />} variant="f1" />
        <PhaseBadge phase="F2" label="F2: Subset Sum" icon={<Layers className="w-3.5 h-3.5" />} variant="f2" />
        <PhaseBadge phase="F3" label="F3: Tolerancia" icon={<ClockIcon className="w-3.5 h-3.5" />} variant="f3" />
        <PhaseBadge phase="F4" label="F4: Localidad" icon={<Moon className="w-3.5 h-3.5" />} variant="f4" />
        <PhaseBadge phase="F5" label="F5: Monto Puro" icon={<Cpu className="w-3.5 h-3.5" />} variant="f4" />
      </div>

      {/* Error alert */}
      {state === "error" && errorMessage && (
        <ErrorAlert message={errorMessage} onDismiss={reset} />
      )}

      {/* Month indicator */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-2 text-muted-foreground text-sm">
          <Calendar className="w-4 h-4 text-primary" />
          <span>Datos de <strong className="text-card-foreground">{mesLabel}</strong></span>
        </div>
        {hasData && !esDatoDelMes && (
          <span className="px-3 py-1 rounded-full text-xs font-medium bg-warning/10 text-warning">
            ⚠ Mostrando última conciliación disponible — sin datos para {mesLabel}
          </span>
        )}
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
        <StatCard title="Total Registros" value={hasData ? totalRegistros.toLocaleString() : "—"} trend={hasData ? `Cuenta: ${cuenta}` : "Sin datos aún"} icon={Database} />
        <StatCard title="Conciliados" value={hasData ? conciliados.toLocaleString() : "—"} trend={hasData ? `${efectividad}% del total` : "Ejecuta una conciliación"} icon={CheckCircle} />
        <StatCard title="Pendientes" value={hasData ? pendientes.toLocaleString() : "—"} trend={hasData ? "Requieren revisión manual" : "—"} icon={Hourglass} />
        <StatCard title="Efectividad" value={hasData ? `${efectividad}%` : "—"} trend={hasData ? `${conciliados.toLocaleString()} de ${totalRegistros.toLocaleString()}` : "—"} icon={ClockIcon} />
      </div>

      {/* Chart */}
      {hasData && (
        <ChartSection conciliados={conciliados} pendientes={pendientes} tasa={tasa} />
      )}

      {/* Action panel */}
      <div className="bg-card rounded-2xl p-6 shadow-card">
        <div className="flex justify-between items-center mb-5">
          <h3 className="text-base font-semibold text-card-foreground flex items-center gap-2">
            <Play className="w-4 h-4 text-primary" />
            Conciliación Bancaria
          </h3>
          {state === "processing" && (
            <span className="px-3 py-1.5 rounded-full text-xs font-medium bg-primary/10 text-primary flex items-center gap-1.5">
              <Loader2 className="w-3 h-3 animate-spin" /> Procesando...
            </span>
          )}
          {state === "success" && (
            <span className="px-3 py-1.5 rounded-full text-xs font-medium bg-success/10 text-success">
              ✓ Completado
            </span>
          )}
        </div>

        <div className="flex gap-1 mb-6">
          {["idle", "processing", "success"].map((s, i) => (
            <div key={i} className={`flex-1 h-2 rounded-full transition-all duration-500 ${
              state === "success" ? "bg-success"
              : state === "processing" && i <= 1 ? "gradient-primary"
              : state !== "idle" && i === 0 ? "bg-success"
              : "bg-border"
            }`} />
          ))}
        </div>

        <div className="flex gap-4 items-center flex-wrap">
          <button
            onClick={() => setActiveSection("ejecutar")}
            className="gradient-primary text-primary-foreground px-6 py-3 rounded-full text-sm font-medium inline-flex items-center gap-2 shadow-lg hover:-translate-y-0.5 transition-all duration-300"
          >
            <Upload className="w-4 h-4" /> Ir a Ejecutar Conciliación
          </button>

          {result?.ruta_reporte && (
            <button
              onClick={() => downloadReport(result.ruta_reporte)}
              className="bg-card text-card-foreground border border-border px-5 py-2.5 rounded-full text-sm inline-flex items-center gap-2 hover:border-primary transition-colors"
            >
              <Download className="w-4 h-4" /> Descargar Reporte
            </button>
          )}

          {hasData && (
            <>
              <button
                onClick={() => setVistaDetalle({ estado: "CONCILIADO", cuenta })}
                className="bg-success/10 text-success px-4 py-2 rounded-full text-sm font-medium inline-flex items-center gap-2 hover:bg-success/20 transition-colors"
              >
                <Eye className="w-4 h-4" /> Ver Conciliados ({conciliados.toLocaleString()})
              </button>
              <button
                onClick={() => setVistaDetalle({ estado: "PENDIENTE", cuenta })}
                className="bg-warning/10 text-warning px-4 py-2 rounded-full text-sm font-medium inline-flex items-center gap-2 hover:bg-warning/20 transition-colors"
              >
                <EyeOff className="w-4 h-4" /> Ver Pendientes ({pendientes.toLocaleString()})
              </button>
            </>
          )}

          {ultimoDelMes && (
            <span className="text-muted-foreground text-[13px] ml-auto flex items-center gap-1.5">
              <ClockIcon className="w-3.5 h-3.5" /> Última: {ultimoDelMes.date}
            </span>
          )}
        </div>
      </div>

      {/* Empty state — solo si no hay NINGÚN historial */}
      {!hasData && history.length === 0 && (
        <div className="bg-card rounded-2xl p-12 shadow-card text-center">
          <FileSpreadsheet className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-card-foreground mb-2">Sin datos para {mesLabel}</h3>
          <p className="text-muted-foreground text-sm mb-6 max-w-md mx-auto">
            Sube un archivo Excel (.xlsx) en la sección "Ejecutar Conciliación" para procesar tus transacciones bancarias.
          </p>
          <button
            onClick={() => setActiveSection("ejecutar")}
            className="gradient-primary text-primary-foreground px-6 py-3 rounded-full text-sm font-medium inline-flex items-center gap-2 shadow-lg hover:-translate-y-0.5 transition-all"
          >
            <Play className="w-4 h-4" /> Comenzar
          </button>
        </div>
      )}

      {/* Hint cuando hay historial pero no del mes seleccionado */}
      {history.length > 0 && !hasData && historialMes.length === 0 && (
        <div className="bg-card rounded-2xl p-6 shadow-card text-center">
          <p className="text-muted-foreground text-sm">
            No hay conciliaciones registradas para <strong className="text-card-foreground">{mesLabel}</strong>.
          </p>
          <p className="text-muted-foreground text-xs mt-2">
            Usa las flechas ← → para navegar al mes con datos, o ejecuta una nueva conciliación.
          </p>
        </div>
      )}

      {/* Recent history for this month */}
      {historialMes.length > 0 && (
        <div className="bg-card rounded-2xl p-6 shadow-card">
          <h3 className="text-base font-semibold text-card-foreground mb-4">Ejecuciones de {mesLabel}</h3>
          <div className="space-y-2">
            {historialMes.slice(0, 5).map((h, i) => (
              <div key={i} className="flex items-center p-4 bg-muted/50 rounded-2xl hover:bg-muted transition-colors">
                <div className="w-[100px] font-medium text-card-foreground text-sm">{h.date}</div>
                <div className="flex-1 flex gap-6">
                  <div className="flex flex-col gap-1">
                    <span className="text-[11px] text-muted-foreground uppercase">Cuenta</span>
                    <span className="text-sm font-semibold text-card-foreground">{h.cuenta}</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[11px] text-muted-foreground uppercase">Total</span>
                    <span className="text-sm font-semibold text-card-foreground">{(h.total ?? 0).toLocaleString()}</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[11px] text-muted-foreground uppercase">Conciliados</span>
                    <span className="text-sm font-semibold text-card-foreground">{(h.conciliados ?? 0).toLocaleString()} ({h.efectividad})</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-[11px] text-muted-foreground uppercase">Pendientes</span>
                    <span className="text-sm font-semibold text-card-foreground">{(h.pendientes ?? 0).toLocaleString()}</span>
                  </div>
                </div>
                {h.ruta_reporte && (
                  <button
                    onClick={() => downloadReport(h.ruta_reporte)}
                    className="px-3 py-1 rounded-full text-xs bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
