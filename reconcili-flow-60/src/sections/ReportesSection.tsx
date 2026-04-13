import { useState } from "react";
import { AlertTriangle, Calendar, RefreshCw, FileSpreadsheet, BarChart2, RotateCcw } from "lucide-react";
import { useReconciliation } from "@/context/ReconciliationContext";
import { useApp, getMonthName } from "@/context/AppContext";
import { ExcelIcon, PdfIcon } from "@/components/FileIcons";
import axios from "axios";
import { toast } from "@/hooks/use-toast";

// ── Iconos de los 4 reportes (gradientes como en la imagen) ──────────────────
function IconConciliacion() {
  return (
    <div className="w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0"
      style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)" }}>
      <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="9" y1="13" x2="9.01" y2="13" strokeWidth="3" strokeLinecap="round"/>
        <text x="11" y="17" fontSize="5" fontWeight="bold" fill="white" stroke="none">X</text>
      </svg>
    </div>
  );
}

function IconMetricas() {
  return (
    <div className="w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0"
      style={{ background: "linear-gradient(135deg, #6d28d9, #4338ca)" }}>
      <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <line x1="3" y1="12" x2="21" y2="12"/>
        <line x1="3" y1="6"  x2="15" y2="6"/>
        <line x1="3" y1="18" x2="18" y2="18"/>
      </svg>
    </div>
  );
}

function IconPendientes() {
  return (
    <div className="w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0"
      style={{ background: "linear-gradient(135deg, #7c3aed, #6366f1)" }}>
      <AlertTriangle className="w-6 h-6 text-white" />
    </div>
  );
}

function IconEvolucion() {
  return (
    <div className="w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0"
      style={{ background: "linear-gradient(135deg, #f97316, #ef4444)" }}>
      <RotateCcw className="w-6 h-6 text-white" />
    </div>
  );
}

// ── Botón de descarga ─────────────────────────────────────────────────────────
function DownloadBtn({ type, onClick, disabled }: {
  type: "excel" | "pdf"; onClick?: () => void; disabled?: boolean;
}) {
  const isExcel = type === "excel";
  return (
    <button
      onClick={onClick}
      disabled={disabled || !onClick}
      className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-medium transition-all border
        ${disabled || !onClick
          ? "opacity-40 cursor-not-allowed border-border text-muted-foreground"
          : isExcel
            ? "border-primary/30 bg-primary/10 text-primary hover:bg-primary/20"
            : "border-red-300 bg-red-50 text-red-600 hover:bg-red-100 dark:bg-red-950/30 dark:border-red-800 dark:text-red-400"
        }`}
    >
      {isExcel ? <ExcelIcon className="w-3.5 h-3.5" /> : <PdfIcon className="w-3.5 h-3.5" />}
      {isExcel ? "Excel" : "PDF"}
    </button>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────
export default function ReportesSection() {
  const { history, downloadReport, downloadReportPdf, getHistoryByMonth, refreshHistorial } = useReconciliation();
  const { currentMonthIndex, currentYear } = useApp();
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);

  const mesLabel = `${getMonthName(currentMonthIndex)} ${currentYear}`;
  const historialMes = getHistoryByMonth(currentMonthIndex, currentYear);
  const entrada = historialMes[0] ?? null;
  const isFallback = !entrada && history.length > 0;
  const dataMes = entrada ?? history[0] ?? null;

  const total       = dataMes?.total       ?? 0;
  const conciliados = dataMes?.conciliados  ?? 0;
  const pendientes  = dataMes?.pendientes   ?? 0;
  const cuenta      = dataMes?.cuenta       ?? null;
  const tasa        = dataMes?.tasa         ?? (total > 0 ? (conciliados / total) * 100 : 0);
  const rutaReporte = dataMes?.ruta_reporte ?? "";
  const idLote      = dataMes?.id_lote      ?? null;
  const hasData     = total > 0 && !!rutaReporte;

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshHistorial();
    setRefreshing(false);
  };

  // Descarga genérica de un endpoint especializado
  const downloadEspecializado = async (endpoint: string, nombre: string, tipo: "xlsx" | "pdf") => {
    if (!idLote || !cuenta) return;
    setLoading(nombre);
    try {
      const mime = tipo === "pdf"
        ? "application/pdf"
        : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      const ext = tipo === "pdf" ? ".pdf" : ".xlsx";
      const res = await axios.get(`/api/${endpoint}/`, {
        params: { id_lote: idLote, cuenta },
        responseType: "blob",
      });
      const url  = window.URL.createObjectURL(new Blob([res.data], { type: mime }));
      const link = document.createElement("a");
      link.href  = url;
      link.setAttribute("download", `${nombre}_${cuenta}${ext}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e: any) {
      toast({ title: "Error de descarga", description: e.message, variant: "destructive" });
    } finally {
      setLoading(null);
    }
  };

  const reportes = [
    {
      IconComp: IconConciliacion,
      title: "Conciliación Completa",
      badge: hasData ? `${conciliados.toLocaleString()} conciliados` : undefined,
      badgeColor: "bg-success/10 text-success",
      desc: "LOGRADO por fase (F1–F7b), grupos, IDs, combinaciones encontradas",
      onExcel: hasData ? () => downloadEspecializado("reporte-conciliacion-completa", "conciliacion_completa", "xlsx") : undefined,
      onPdf:   hasData ? () => downloadEspecializado("reporte-conciliacion-completa-pdf", "conciliacion_completa", "pdf") : undefined,
    },
    {
      IconComp: IconMetricas,
      title: "Métricas por Fase (F1–F7b)",
      badge: hasData ? `${tasa.toFixed(1)}% efectividad` : undefined,
      badgeColor: "bg-primary/10 text-primary",
      desc: "Grupos, transacciones, cobertura de negativos por cada fase del motor",
      onExcel: hasData ? () => downloadEspecializado("reporte-metricas-fases", "metricas_fases", "xlsx") : undefined,
      onPdf:   hasData ? () => downloadEspecializado("reporte-metricas-fases-pdf", "metricas_fases", "pdf") : undefined,
    },
    {
      IconComp: IconPendientes,
      title: "Pendientes y Anomalías",
      badge: hasData ? `${pendientes.toLocaleString()} pendientes` : undefined,
      badgeColor: "bg-warning/10 text-warning",
      desc: "Negativos sin cubrir, con/sin contraparte, análisis de irresolubles matemáticos",
      onExcel: hasData ? () => downloadEspecializado("reporte-pendientes", "pendientes_anomalias", "xlsx") : undefined,
      onPdf:   hasData ? () => downloadEspecializado("reporte-pendientes-pdf", "pendientes_anomalias", "pdf") : undefined,
    },
    {
      IconComp: IconEvolucion,
      title: "Evolución del Motor v1 → v4",
      badge: "Histórico",
      badgeColor: "bg-orange-500/10 text-orange-500",
      desc: "Comparativa de tasas: 71% → 76% → 86% → 99.9% — historia de bugs corregidos",
      onExcel: undefined,
      onPdf:   hasData ? () => downloadEspecializado("reporte-evolucion-pdf", "evolucion_motor", "pdf") : undefined,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="bg-card rounded-2xl p-6 shadow-card">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold text-card-foreground">Exportar Reportes</h3>
          <button
            onClick={handleRefresh}
            className="px-3 py-1.5 rounded-full text-xs bg-primary/10 text-primary hover:bg-primary/20 transition-colors flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} /> Actualizar
          </button>
        </div>

        {/* Mes */}
        <div className="flex items-center gap-2 mb-6">
          <Calendar className="w-4 h-4 text-primary" />
          <span className="text-sm text-muted-foreground">
            Datos de <strong className="text-card-foreground">{mesLabel}</strong>
            {hasData && cuenta && <span className="ml-2">— Cuenta {cuenta} — {total.toLocaleString()} registros</span>}
          </span>
          {isFallback && (
            <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-warning/10 text-warning">
              ⚠ Última conciliación disponible
            </span>
          )}
        </div>

        {!hasData && (
          <div className="bg-muted/50 rounded-2xl p-6 text-center mb-4">
            <FileSpreadsheet className="w-10 h-10 text-muted-foreground/30 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              No hay conciliaciones para <strong className="text-card-foreground">{mesLabel}</strong>.
            </p>
          </div>
        )}

        {/* Lista */}
        <div className="space-y-3">
          {reportes.map((r, i) => {
            const isLoading = loading === r.title;
            return (
              <div key={i} className={`flex items-center p-5 rounded-2xl border transition-colors
                ${!hasData && i < 3 ? "opacity-60" : ""}
                bg-muted/50 border-border hover:border-primary/30`}
              >
                <r.IconComp />
                <div className="flex-1 min-w-0 mx-4">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <h4 className="text-sm font-semibold text-card-foreground">{r.title}</h4>
                    {r.badge && (
                      <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${r.badgeColor}`}>
                        {r.badge}
                      </span>
                    )}
                  </div>
                  <p className="text-[12px] text-muted-foreground">{r.desc}</p>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  {r.onExcel !== undefined && (
                    <DownloadBtn type="excel" onClick={r.onExcel} disabled={!hasData || isLoading} />
                  )}
                  <DownloadBtn type="pdf" onClick={r.onPdf} disabled={!hasData || isLoading} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Estructura del Excel */}
      {hasData && (
        <div className="bg-card rounded-2xl p-6 shadow-card">
          <div className="flex items-center gap-2 mb-4">
            <BarChart2 className="w-4 h-4 text-primary" />
            <h4 className="text-sm font-semibold text-card-foreground">Estructura del Excel generado</h4>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {[
              { hoja: "RESUMEN",    desc: "Estadísticas globales y desglose por fase" },
              { hoja: "F1",         desc: "Fast-Pass — 1:1 exacto" },
              { hoja: "F2",         desc: "Subset Sum — N:N suma cero" },
              { hoja: "F3",         desc: "Tolerancia ±5 centavos" },
              { hoja: "F4",         desc: "Monto + Localidad" },
              { hoja: "F5",         desc: "Monto Puro Global" },
              { hoja: "F6",         desc: "Subset Sum Global" },
              { hoja: "F7 / F7b",   desc: "Final Cleaning" },
              { hoja: "LOGRADO",    desc: "Todos los conciliados + Fase" },
              { hoja: "PENDIENTES", desc: "Todos los sin conciliar" },
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
