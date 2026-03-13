import { useState } from "react";
import { FileSpreadsheet, BarChart3, AlertTriangle, Download, CheckCircle, Eye, EyeOff, Layers, X, Calendar } from "lucide-react";
import { useReconciliation } from "@/context/ReconciliationContext";
import { useApp, getMonthName } from "@/context/AppContext";
import TransaccionesTable from "@/components/TransaccionesTable";

export default function ReportesSection() {
  const { history, downloadReport, getHistoryByMonth, result } = useReconciliation();
  const { currentMonthIndex, currentYear } = useApp();
  const [vistaDetalle, setVistaDetalle] = useState<{ estado: "CONCILIADO" | "PENDIENTE"; cuenta: string; titulo: string } | null>(null);

  const mesLabel = `${getMonthName(currentMonthIndex)} ${currentYear}`;
  const historialMes = getHistoryByMonth(currentMonthIndex, currentYear);
  const ultimoDelMes = historialMes[0] ?? null;
  const esMesActual = result?.mes === currentMonthIndex && result?.anio === currentYear;

  const dataMes: any = esMesActual ? result : ultimoDelMes ?? result ?? history[0] ?? null;
  const esDatoDelMes = esMesActual || !!ultimoDelMes;

  const total       = dataMes?.total_leido ?? dataMes?.total ?? 0;
  const conciliados = dataMes?.conciliados ?? 0;
  const pendientes  = dataMes?.pendientes  ?? 0;
  const cuenta      = dataMes?.cuenta_procesada ?? dataMes?.cuenta ?? null;
  const tasa        = dataMes?.tasa_conciliacion ?? dataMes?.tasa ?? (total > 0 ? (conciliados / total) * 100 : 0);
  const hasData     = total > 0;
  const rutaReporte = dataMes?.ruta_reporte ?? "";

  if (vistaDetalle) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <button onClick={() => setVistaDetalle(null)} className="flex items-center gap-2 px-4 py-2 rounded-full bg-muted text-muted-foreground text-sm hover:bg-muted/80 transition-colors">
            <X className="w-4 h-4" /> Volver a Reportes
          </button>
          <span className="text-sm text-muted-foreground">{vistaDetalle.titulo} — {mesLabel}</span>
        </div>
        <TransaccionesTable estado={vistaDetalle.estado} cuenta={vistaDetalle.cuenta} onClose={() => setVistaDetalle(null)} />
      </div>
    );
  }

  const reports = [
    {
      icon: CheckCircle, color: "bg-success/10", iconColor: "text-success",
      title: "Registros Conciliados",
      desc: hasData ? `${conciliados.toLocaleString()} transacciones conciliadas — ${tasa.toFixed(1)}% de efectividad` : "Ejecuta una conciliación para ver los registros conciliados",
      badge: hasData ? `${tasa.toFixed(1)}%` : null, badgeColor: "bg-success/10 text-success",
      actions: hasData && cuenta ? [
        { label: "Ver en pantalla", icon: Eye, onClick: () => setVistaDetalle({ estado: "CONCILIADO", cuenta, titulo: "Registros Conciliados" }), style: "bg-success/10 text-success hover:bg-success/20" },
        { label: "Descargar Excel", icon: Download, onClick: () => rutaReporte && downloadReport(rutaReporte), style: "bg-card text-muted-foreground border border-border hover:border-success" },
      ] : [],
    },
    {
      icon: AlertTriangle, color: "bg-warning/10", iconColor: "text-warning",
      title: "Registros Pendientes",
      desc: hasData ? `${pendientes.toLocaleString()} transacciones sin conciliar que requieren revisión manual` : "Sin datos disponibles",
      badge: hasData ? `${pendientes.toLocaleString()} pend.` : null, badgeColor: "bg-warning/10 text-warning",
      actions: hasData && cuenta ? [
        { label: "Ver en pantalla", icon: EyeOff, onClick: () => setVistaDetalle({ estado: "PENDIENTE", cuenta, titulo: "Registros Pendientes" }), style: "bg-warning/10 text-warning hover:bg-warning/20" },
        { label: "Descargar Excel", icon: Download, onClick: () => rutaReporte && downloadReport(rutaReporte), style: "bg-card text-muted-foreground border border-border hover:border-warning" },
      ] : [],
    },
    {
      icon: BarChart3, color: "bg-primary/10", iconColor: "text-primary",
      title: "Reporte Completo con Fases",
      desc: hasData ? "Excel con 8 hojas: RESUMEN, F1, F2, F3, F4, F5, LOGRADO y PENDIENTES" : "Contiene el desglose por cada fase del motor de conciliación",
      badge: hasData ? "8 hojas" : null, badgeColor: "bg-primary/10 text-primary",
      actions: hasData && rutaReporte ? [
        { label: "Descargar Excel completo", icon: Download, onClick: () => downloadReport(rutaReporte), style: "gradient-primary text-primary-foreground shadow-lg hover:-translate-y-0.5" },
      ] : [],
    },
    {
      icon: Layers, color: "bg-muted", iconColor: "text-muted-foreground",
      title: "Resumen General",
      desc: hasData ? `Cuenta ${cuenta} — ${total.toLocaleString()} registros — Efectividad ${tasa.toFixed(1)}% — Conciliados: ${conciliados.toLocaleString()} | Pendientes: ${pendientes.toLocaleString()}` : "Estadísticas generales del proceso",
      badge: hasData ? `${total.toLocaleString()} regs.` : null, badgeColor: "bg-muted text-muted-foreground",
      actions: hasData && rutaReporte ? [
        { label: "Descargar Excel", icon: Download, onClick: () => downloadReport(rutaReporte), style: "bg-card text-muted-foreground border border-border hover:border-primary" },
      ] : [],
    },
  ];

  return (
    <div className="space-y-6">
      <div className="bg-card rounded-2xl p-6 shadow-card">
        <div className="flex items-center gap-2 mb-1">
          <FileSpreadsheet className="w-5 h-5 text-primary" />
          <h3 className="text-lg font-semibold text-card-foreground">Reportes de {mesLabel}</h3>
          {hasData && !esDatoDelMes && (
            <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-warning/10 text-warning">⚠ Última conciliación disponible</span>
          )}
        </div>
        <p className="text-muted-foreground text-sm mb-6">
          {hasData ? `Cuenta ${cuenta} — ${total.toLocaleString()} registros` : "Ejecuta una conciliación para habilitar los reportes"}
        </p>

        <div className="space-y-3">
          {reports.map((r, i) => (
            <div key={i} className="flex items-center p-5 bg-muted/50 rounded-2xl border border-border">
              <div className={`w-12 h-12 rounded-2xl ${r.color} flex items-center justify-center mr-4 flex-shrink-0`}>
                <r.icon className={`w-5 h-5 ${r.iconColor}`} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <h4 className="text-base font-semibold text-card-foreground">{r.title}</h4>
                  {r.badge && <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${r.badgeColor}`}>{r.badge}</span>}
                </div>
                <p className="text-[13px] text-muted-foreground">{r.desc}</p>
              </div>
              {r.actions.length > 0 && (
                <div className="flex gap-2 flex-shrink-0 ml-4">
                  {r.actions.map((action, j) => (
                    <button key={j} onClick={action.onClick} className={`px-4 py-2 rounded-full text-xs inline-flex items-center gap-1.5 transition-all ${action.style}`}>
                      <action.icon className="w-3.5 h-3.5" /> {action.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {hasData && (
        <div className="bg-card rounded-2xl p-6 shadow-card">
          <div className="flex items-center gap-2 mb-4">
            <Layers className="w-4 h-4 text-primary" />
            <h4 className="text-sm font-semibold text-card-foreground">Estructura del Excel generado</h4>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {[
              { hoja: "RESUMEN",    desc: "Estadísticas y desglose por fase" },
              { hoja: "F1",         desc: "Conciliados Fast-Pass (1:1 exacto)" },
              { hoja: "F2",         desc: "Conciliados Subset Sum (N:N)" },
              { hoja: "F3",         desc: "Conciliados Tolerancia ±5 cts" },
              { hoja: "F4",         desc: "Conciliados Monto + Localidad" },
              { hoja: "F5",         desc: "Conciliados Monto Puro Global" },
              { hoja: "LOGRADO",    desc: "Todos los conciliados con columna Fase" },
              { hoja: "PENDIENTES", desc: "Todos los registros sin conciliar" },
            ].map((h, i) => (
              <div key={i} className="bg-muted/50 rounded-xl p-3 border border-border">
                <span className="text-xs font-mono font-semibold text-primary">{h.hoja}</span>
                <p className="text-[11px] text-muted-foreground mt-0.5">{h.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
