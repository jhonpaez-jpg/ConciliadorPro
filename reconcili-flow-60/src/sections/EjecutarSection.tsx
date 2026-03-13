import { Play, Clock, Loader2, CheckCircle, RotateCcw, Download, Eye, EyeOff } from "lucide-react";
import Dropzone from "@/components/Dropzone";
import StatCard from "@/components/StatCard";
import ChartSection from "@/components/ChartSection";
import ErrorAlert from "@/components/ErrorAlert";
import TransaccionesTable from "@/components/TransaccionesTable";
import { useReconciliation, ReconciliationConfig } from "@/context/ReconciliationContext";
import { cn } from "@/lib/utils";
import { useState } from "react";

const CONFIG_FIELDS: { key: keyof ReconciliationConfig; label: string; min: number; max: number; defaultVal: number; unit: string }[] = [
  { key: "f2Timeout", label: "Fase 2 timeout", min: 1, max: 10, defaultVal: 2, unit: "seg" },
  { key: "f3Timeout", label: "Fase 3 timeout", min: 5, max: 30, defaultVal: 10, unit: "seg" },
  { key: "f4Timeout", label: "Fase 4 timeout", min: 15, max: 120, defaultVal: 30, unit: "seg" },
  { key: "maxDepth", label: "Profundidad máxima", min: 2, max: 10, defaultVal: 5, unit: "niveles" },
];

export default function EjecutarSection() {
  const { state, result, file, setFile, errorMessage, progressMessage, uploadAndReconcile, downloadReport, reset } = useReconciliation();
  const [config, setConfig] = useState<ReconciliationConfig>({
    f2Timeout: 2,
    f3Timeout: 10,
    f4Timeout: 30,
    maxDepth: 5,
  });
  const [vistaDetalle, setVistaDetalle] = useState<"conciliados" | "pendientes" | null>(null);

  const handleStart = () => {
    if (file) uploadAndReconcile(file, config);
  };

  const cuenta = result?.cuenta_procesada ?? "—";

  return (
    <div className="space-y-6">
      {/* Transaction detail view */}
      {vistaDetalle && result && (
        <TransaccionesTable
          estado={vistaDetalle === "conciliados" ? "CONCILIADO" : "PENDIENTE"}
          cuenta={cuenta}
          onClose={() => setVistaDetalle(null)}
        />
      )}

      <div className="bg-card rounded-2xl p-6 shadow-card">
        <h3 className="text-lg font-semibold text-card-foreground mb-5">Nueva Ejecución de Conciliación</h3>

        {state === "error" && errorMessage && (
          <div className="mb-6">
            <ErrorAlert message={errorMessage} onDismiss={reset} />
          </div>
        )}

        <div className="mb-6">
          <Dropzone file={file} onFileSelect={setFile} onClear={() => setFile(null)} />
        </div>

        {/* Config */}
        <div className="bg-muted/50 rounded-2xl p-5 mb-6">
          <h4 className="font-medium text-card-foreground mb-4">Configuración de ejecución</h4>
          <div className="grid grid-cols-2 gap-5">
            {CONFIG_FIELDS.map(({ key, label, min, max, unit }) => (
              <div key={key}>
                <label className="block mb-2 text-[13px] text-muted-foreground">{label}</label>
                <input
                  type="number"
                  min={min}
                  max={max}
                  value={config[key]}
                  onChange={(e) => setConfig((prev) => ({ ...prev, [key]: Number(e.target.value) }))}
                  className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-ring text-card-foreground"
                />
                <p className="text-[11px] text-muted-foreground mt-1">
                  Rango: {min}–{max} {unit}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          {state === "idle" && (
            <>
              <button
                onClick={handleStart}
                disabled={!file}
                className={cn(
                  "flex-1 gradient-primary text-primary-foreground py-3 rounded-full text-sm font-medium inline-flex items-center justify-center gap-2 shadow-lg transition-all",
                  file ? "hover:-translate-y-0.5" : "opacity-50 cursor-not-allowed"
                )}
              >
                <Play className="w-4 h-4" /> Iniciar Conciliación
              </button>
              <button className="flex-1 bg-card text-muted-foreground border border-border py-3 rounded-full text-sm inline-flex items-center justify-center gap-2 hover:border-primary transition-colors">
                <Clock className="w-4 h-4" /> Programar para nocturno
              </button>
            </>
          )}
          {state === "processing" && (
            <div className="flex-1 flex items-center justify-center gap-3 py-3">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
              <span className="text-sm text-muted-foreground">{progressMessage || "Procesando conciliación..."}</span>
            </div>
          )}
          {(state === "success" || state === "error") && (
            <button
              onClick={reset}
              className="flex-1 bg-card text-muted-foreground border border-border py-3 rounded-full text-sm inline-flex items-center justify-center gap-2 hover:border-primary transition-colors"
            >
              <RotateCcw className="w-4 h-4" /> Limpiar Vista / Nueva Carga
            </button>
          )}
        </div>

        {/* Skeleton loading */}
        {state === "processing" && (
          <div className="mt-6 space-y-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-20 bg-muted/50 rounded-2xl animate-skeleton" style={{ animationDelay: `${i * 0.2}s` }} />
            ))}
          </div>
        )}
      </div>

      {/* Results */}
      {state === "success" && result && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-5">
            <StatCard title="Cuenta Procesada" value={cuenta} icon={CheckCircle} />
            <StatCard
              title="Efectividad"
              value={`${(result.tasa_conciliacion ?? ((result.total_leido ?? 0) > 0 ? (((result.conciliados ?? 0) / (result.total_leido ?? 1)) * 100) : 0)).toFixed(1)}%`}
              trend={`${(result.conciliados ?? 0).toLocaleString()} de ${(result.total_leido ?? 0).toLocaleString()} registros`}
              icon={CheckCircle}
            />
            <StatCard title="Grupos Match" value={(result.conciliados ?? 0).toLocaleString()} icon={CheckCircle} />
            <StatCard title="Pendientes" value={(result.pendientes ?? 0).toLocaleString()} trend="Requieren revisión manual" icon={Clock} />
          </div>

          <ChartSection conciliados={result.conciliados ?? 0} pendientes={result.pendientes ?? 0} tasa={result.tasa_conciliacion} />

          <div className="flex justify-end gap-3">
            <button
              onClick={() => setVistaDetalle("conciliados")}
              className="bg-success/10 text-success px-5 py-2.5 rounded-full text-sm font-medium inline-flex items-center gap-2 hover:bg-success/20 transition-colors"
            >
              <Eye className="w-4 h-4" /> Ver Conciliados ({(result.conciliados ?? 0).toLocaleString()})
            </button>
            <button
              onClick={() => setVistaDetalle("pendientes")}
              className="bg-warning/10 text-warning px-5 py-2.5 rounded-full text-sm font-medium inline-flex items-center gap-2 hover:bg-warning/20 transition-colors"
            >
              <EyeOff className="w-4 h-4" /> Ver Pendientes ({(result.pendientes ?? 0).toLocaleString()})
            </button>
            {result.ruta_reporte && (
              <button
                onClick={() => downloadReport(result.ruta_reporte)}
                className="gradient-primary text-primary-foreground px-6 py-3 rounded-full text-sm font-medium inline-flex items-center gap-2 shadow-lg hover:-translate-y-0.5 transition-all"
              >
                <Download className="w-4 h-4" /> Descargar Excel
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
