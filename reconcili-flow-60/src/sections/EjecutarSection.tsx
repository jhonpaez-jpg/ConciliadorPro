import {
  Play,
  Clock,
  Loader2,
  CheckCircle,
  RotateCcw,
  Eye,
  EyeOff,
  CalendarClock,
  X,
  AlertCircle,
  Info,
} from "lucide-react";
import { ExcelIcon, PdfIcon } from "@/components/FileIcons";
import Dropzone from "@/components/Dropzone";
import StatCard from "@/components/StatCard";
import ChartSection from "@/components/ChartSection";
import ErrorAlert from "@/components/ErrorAlert";
import TransaccionesTable from "@/components/TransaccionesTable";
import {
  useReconciliation,
  ReconciliationConfig,
} from "@/context/ReconciliationContext";
import { cn } from "@/lib/utils";
import { useState, useRef } from "react";
import { useNotifications } from "@/hooks/useNotifications";
import axios from "axios";

const CONFIG_FIELDS: {
  key: keyof ReconciliationConfig;
  label: string;
  min: number;
  max: number;
  defaultVal: number;
  unit: string;
}[] = [
  {
    key: "f2Timeout",
    label: "Fase 2 timeout",
    min: 1,
    max: 10,
    defaultVal: 2,
    unit: "seg",
  },
  {
    key: "f3Timeout",
    label: "Fase 3 timeout",
    min: 5,
    max: 30,
    defaultVal: 10,
    unit: "seg",
  },
  {
    key: "f4Timeout",
    label: "Fase 4 timeout",
    min: 15,
    max: 120,
    defaultVal: 30,
    unit: "seg",
  },
  {
    key: "maxDepth",
    label: "Profundidad máxima",
    min: 2,
    max: 10,
    defaultVal: 5,
    unit: "niveles",
  },
];

// Estima el % de progreso según el mensaje del backend
function getProgressPct(msg: string): number {
  const m = msg.toLowerCase();
  if (!msg || m.includes("subiendo")) return 5;
  if (m.includes("leyendo") || m.includes("filtrando")) return 10;
  if (m.includes("insertando")) return 18;
  if (m.includes("f1-f4") && !m.includes("[")) return 22;
  if (m.includes("f1-f4") && m.includes("[")) {
    // "F1-F4 [3/12] Localidad..." → extraer progreso
    const match = m.match(/\[(\d+)\/(\d+)\]/);
    if (match) {
      const pct = parseInt(match[1]) / parseInt(match[2]);
      return Math.round(22 + pct * 38); // 22% → 60%
    }
    return 30;
  }
  if (m.includes("f6") || m.includes("subset")) return 65;
  if (m.includes("f5") || m.includes("monto puro")) return 80;
  if (m.includes("generando reporte")) return 90;
  if (m.includes("procesando")) return 15;
  return 50;
}

// Valida que el archivo Excel tenga solo un período (ej: 2026/001)
// Llama al backend que lee el Excel correctamente con Polars
async function validarPeriodoUnico(
  file: File,
): Promise<{ ok: boolean; periodos: string[]; mensaje: string }> {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await axios.post("/api/validar-archivo/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 15_000,
    });
    return {
      ok: data.ok ?? true,
      periodos: data.periodos ?? [],
      mensaje: data.mensaje ?? "",
    };
  } catch {
    // Si el endpoint falla (backend no disponible), dejar pasar
    return { ok: true, periodos: [], mensaje: "" };
  }
}

export default function EjecutarSection() {
  const {
    state,
    result,
    file,
    setFile,
    errorMessage,
    progressMessage,
    uploadAndReconcile,
    cancelReconciliation,
    downloadReport,
    downloadReportPdf,
    reset,
    config,
    setConfig,
    scheduleReconciliation,
  } = useReconciliation();

  const [vistaDetalle, setVistaDetalle] = useState<
    "conciliados" | "pendientes" | null
  >(null);
  const [cancelling, setCancelling] = useState(false);
  const [showSchedule, setShowSchedule] = useState(false);
  const [periodError, setPeriodError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const progressRef = useRef(0); // valor suavizado de la barra

  // Inicializar notificaciones
  useNotifications();
  const [schedFecha, setSchedFecha] = useState(
    () => new Date().toISOString().split("T")[0],
  );
  const [schedHora, setSchedHora] = useState(() => {
    // Hora por defecto: ahora + 5 minutos
    const d = new Date(Date.now() + 5 * 60 * 1000);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  });
  const [scheduling, setScheduling] = useState(false);

  // Hora mínima: si es hoy, no permitir horas pasadas
  const today = new Date().toISOString().split("T")[0];
  const isToday = schedFecha === today;
  const nowPlus1 = (() => {
    const d = new Date(Date.now() + 60 * 1000); // +1 min de margen
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  })();
  const minHora = isToday ? nowPlus1 : "00:00";

  // Cuando cambia la fecha a hoy, ajustar la hora si ya pasó
  const handleFechaChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nuevaFecha = e.target.value;
    setSchedFecha(nuevaFecha);
    if (nuevaFecha === today && schedHora < nowPlus1) {
      setSchedHora(nowPlus1);
    }
  };

  // Tiempo restante para mostrar en el modal
  const dtProg = new Date(`${schedFecha}T${schedHora}:00`);
  const segsRestantes = Math.max(
    0,
    Math.floor((dtProg.getTime() - Date.now()) / 1000),
  );
  const horasRestantes = Math.floor(segsRestantes / 3600);
  const minsRestantes = Math.floor((segsRestantes % 3600) / 60);
  const tiempoLabel =
    segsRestantes <= 0
      ? "Se ejecutará de inmediato"
      : horasRestantes > 0
        ? `En ${horasRestantes}h ${minsRestantes}m`
        : `En ${minsRestantes} minuto${minsRestantes !== 1 ? "s" : ""}`;

  const handleStart = async () => {
    if (!file) return;
    progressRef.current = 0; // resetear barra
    // Validar período único antes de ejecutar
    setValidating(true);
    setPeriodError(null);
    const { ok, periodos, mensaje } = await validarPeriodoUnico(file);
    setValidating(false);
    if (!ok) {
      setPeriodError(
        mensaje ||
          `El archivo contiene múltiples períodos: ${periodos.join(", ")}.`,
      );
      return;
    }
    uploadAndReconcile(file, config);
  };

  const handleCancel = async () => {
    setCancelling(true);
    await cancelReconciliation();
    setCancelling(false);
  };

  const handleSchedule = async () => {
    if (!file) return;
    setScheduling(true);
    try {
      await scheduleReconciliation(file, schedFecha, schedHora, config);
      setShowSchedule(false);
    } finally {
      setScheduling(false);
    }
  };

  // Solo usar result de la sesión actual — no persiste al recargar
  const cuenta = result?.cuenta_procesada ?? "—";
  const conciliados = result?.conciliados ?? 0;
  const pendientes = result?.pendientes ?? 0;
  const totalLeido = result?.total_leido ?? 0;
  const tasa = result?.tasa_conciliacion ?? 0;
  const rutaReporte = result?.ruta_reporte ?? "";

  return (
    <div className="space-y-6">
      {/* Modal programar ejecución */}
      {showSchedule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-card rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-card-foreground flex items-center gap-2">
                <CalendarClock className="w-5 h-5 text-primary" /> Programar
                Ejecución Nocturna
              </h3>
              <button
                onClick={() => setShowSchedule(false)}
                className="p-1.5 rounded-lg hover:bg-muted transition-colors"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>

            <div className="bg-muted/50 rounded-xl p-3 text-sm text-muted-foreground">
              Archivo:{" "}
              <strong className="text-card-foreground">{file?.name}</strong>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-muted-foreground mb-1.5">
                  Fecha
                </label>
                <input
                  type="date"
                  value={schedFecha}
                  min={today}
                  onChange={handleFechaChange}
                  className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1.5">
                  Hora{" "}
                  {isToday && (
                    <span className="text-primary">(mín. {minHora})</span>
                  )}
                </label>
                <input
                  type="time"
                  value={schedHora}
                  min={minHora}
                  onChange={(e) => setSchedHora(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>

            {/* Resumen de tiempo */}
            <div
              className={`rounded-xl p-3 text-sm flex items-center gap-2 ${
                segsRestantes <= 0
                  ? "bg-warning/10 text-warning"
                  : "bg-primary/5 text-primary"
              }`}
            >
              <CalendarClock className="w-4 h-4 shrink-0" />
              <span>
                <strong>{tiempoLabel}</strong>
                {segsRestantes > 0 && (
                  <span className="text-muted-foreground ml-1">
                    — {schedFecha} a las {schedHora}
                  </span>
                )}
              </span>
            </div>

            <p className="text-xs text-muted-foreground">
              Aparecerá en el Historial como "Programado" hasta que se complete.
              Si el servidor se reinicia, la conciliación se retomará
              automáticamente.
            </p>

            <div className="flex gap-3">
              <button
                onClick={() => setShowSchedule(false)}
                className="flex-1 bg-card border border-border text-muted-foreground py-2.5 rounded-full text-sm hover:border-primary transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleSchedule}
                disabled={scheduling}
                className="flex-1 gradient-primary text-primary-foreground py-2.5 rounded-full text-sm font-medium inline-flex items-center justify-center gap-2 shadow-lg hover:-translate-y-0.5 transition-all disabled:opacity-60"
              >
                {scheduling ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <CalendarClock className="w-4 h-4" />
                )}
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tabla de detalle — reemplaza la vista al abrirse */}
      {vistaDetalle && result && (
        <TransaccionesTable
          estado={vistaDetalle === "conciliados" ? "CONCILIADO" : "PENDIENTE"}
          cuenta={cuenta}
          onClose={() => setVistaDetalle(null)}
        />
      )}

      {!vistaDetalle && (
        <>
          <div className="bg-card rounded-2xl p-6 shadow-card">
            <h3 className="text-lg font-semibold text-card-foreground mb-5">
              Nueva Ejecución de Conciliación
            </h3>

            {/* Aviso permanente */}
            <div className="flex items-start gap-3 p-4 bg-primary/5 border border-primary/20 rounded-2xl mb-5">
              <Info className="w-4 h-4 text-primary shrink-0 mt-0.5" />
              <p className="text-xs text-muted-foreground leading-relaxed">
                <strong className="text-card-foreground">Importante:</strong>{" "}
                Sube únicamente archivos con datos de{" "}
                <strong className="text-card-foreground">
                  un solo período contable
                </strong>{" "}
                (ej: 2026/001). No mezcles datos de meses distintos en el mismo
                archivo. El motor procesa por período para garantizar la
                integridad de la conciliación.
              </p>
            </div>

            {/* Error de período */}
            {periodError && (
              <div className="flex items-start gap-3 p-4 bg-destructive/5 border border-destructive/30 rounded-2xl mb-5">
                <AlertCircle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-destructive mb-1">
                    Archivo con múltiples períodos
                  </p>
                  <p className="text-xs text-muted-foreground">{periodError}</p>
                </div>
                <button
                  onClick={() => setPeriodError(null)}
                  className="ml-auto p-1 hover:bg-destructive/10 rounded-lg transition-colors"
                >
                  <X className="w-3.5 h-3.5 text-destructive" />
                </button>
              </div>
            )}

            {state === "error" && errorMessage && (
              <div className="mb-6">
                <ErrorAlert message={errorMessage} onDismiss={reset} />
              </div>
            )}

            <div className="mb-6">
              <Dropzone
                file={file}
                onFileSelect={setFile}
                onClear={() => setFile(null)}
              />
            </div>

            {/* Config */}
            <div className="bg-muted/50 rounded-2xl p-5 mb-6">
              <h4 className="font-medium text-card-foreground mb-4">
                Configuración de ejecución
              </h4>
              <div className="grid grid-cols-2 gap-5">
                {CONFIG_FIELDS.map(({ key, label, min, max, unit }) => (
                  <div key={key}>
                    <label className="block mb-2 text-[13px] text-muted-foreground">
                      {label}
                    </label>
                    <input
                      type="number"
                      min={min}
                      max={max}
                      value={config[key]}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          [key]: Number(e.target.value),
                        } as ReconciliationConfig)
                      }
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
            <div className="flex gap-3 flex-wrap">
              {state === "idle" && (
                <>
                  <button
                    onClick={handleStart}
                    disabled={!file || validating}
                    className={cn(
                      "flex-1 gradient-primary text-primary-foreground py-3 rounded-full text-sm font-medium inline-flex items-center justify-center gap-2 shadow-lg transition-all",
                      file && !validating
                        ? "hover:-translate-y-0.5"
                        : "opacity-50 cursor-not-allowed",
                    )}
                  >
                    {validating ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" /> Validando
                        archivo...
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4" /> Iniciar Conciliación
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => setShowSchedule(true)}
                    disabled={!file}
                    className={cn(
                      "flex-1 bg-card text-muted-foreground border border-border py-3 rounded-full text-sm inline-flex items-center justify-center gap-2 hover:border-primary transition-colors",
                      !file && "opacity-50 cursor-not-allowed",
                    )}
                  >
                    <CalendarClock className="w-4 h-4" /> Programar para
                    nocturno
                  </button>
                </>
              )}

              {state === "processing" && (
                <div className="flex-1 flex items-center gap-3">
                  {/* Bloque de progreso con barra verde animada */}
                  <div className="relative flex-1 overflow-hidden rounded-xl border border-border bg-muted/50 h-12">
                    {/* Barra de progreso verde — solo avanza, nunca retrocede */}
                    {(() => {
                      const target = getProgressPct(progressMessage);
                      // Suavizar: solo avanzar
                      if (target > progressRef.current)
                        progressRef.current = target;
                      return (
                        <div
                          className="absolute inset-y-0 left-0 bg-success/20 rounded-xl"
                          style={{
                            width: `${progressRef.current}%`,
                            transition: "width 2s cubic-bezier(0.4, 0, 0.2, 1)",
                          }}
                        />
                      );
                    })()}
                    {/* Contenido: spinner + texto centrado */}
                    <div className="relative z-10 h-full flex items-center justify-center gap-2 px-4">
                      <Loader2 className="w-4 h-4 animate-spin text-primary shrink-0" />
                      <span className="text-sm text-card-foreground font-medium text-center truncate">
                        {progressMessage || "Procesando conciliación..."}
                      </span>
                    </div>
                  </div>

                  {/* Botón cancelar a la derecha */}
                  <button
                    onClick={handleCancel}
                    disabled={cancelling}
                    className="shrink-0 h-12 px-5 rounded-xl text-sm font-medium inline-flex items-center gap-2 bg-destructive/10 text-destructive hover:bg-destructive/20 transition-colors border border-destructive/30 disabled:opacity-50"
                  >
                    {cancelling ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : null}
                    Cancelar
                  </button>
                </div>
              )}

              {(state === "success" || state === "error") && (
                <button
                  onClick={reset}
                  className="flex-1 bg-card text-muted-foreground border border-border py-3 rounded-full text-sm inline-flex items-center justify-center gap-2 hover:border-primary transition-colors"
                >
                  <RotateCcw className="w-4 h-4" /> Nueva Carga
                </button>
              )}
            </div>

            {/* Skeleton loading */}
            {state === "processing" && (
              <div className="mt-6 space-y-4">
                {[...Array(4)].map((_, i) => (
                  <div
                    key={i}
                    className="h-20 bg-muted/50 rounded-2xl animate-skeleton"
                    style={{ animationDelay: `${i * 0.2}s` }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Resultados — SOLO cuando state === "success", desaparecen al recargar */}
          {state === "success" && result && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 xl:grid-cols-4 gap-5">
                <StatCard
                  title="Cuenta Procesada"
                  value={cuenta}
                  icon={CheckCircle}
                />
                <StatCard
                  title="Efectividad"
                  value={`${tasa > 0 ? tasa.toFixed(1) : totalLeido > 0 ? ((conciliados / totalLeido) * 100).toFixed(1) : "0"}%`}
                  trend={`${conciliados.toLocaleString()} de ${totalLeido.toLocaleString()} registros`}
                  icon={CheckCircle}
                />
                <StatCard
                  title="Conciliados"
                  value={conciliados.toLocaleString()}
                  icon={CheckCircle}
                />
                <StatCard
                  title="Pendientes"
                  value={pendientes.toLocaleString()}
                  trend="Requieren revisión manual"
                  icon={Clock}
                />
              </div>

              <ChartSection
                conciliados={conciliados}
                pendientes={pendientes}
                tasa={tasa}
              />

              <div className="flex justify-end gap-3 flex-wrap">
                <button
                  onClick={() => setVistaDetalle("conciliados")}
                  className="bg-success/10 text-success px-5 py-2.5 rounded-full text-sm font-medium inline-flex items-center gap-2 hover:bg-success/20 transition-colors"
                >
                  <Eye className="w-4 h-4" /> Ver Conciliados (
                  {conciliados.toLocaleString()})
                </button>
                <button
                  onClick={() => setVistaDetalle("pendientes")}
                  className="bg-warning/10 text-warning px-5 py-2.5 rounded-full text-sm font-medium inline-flex items-center gap-2 hover:bg-warning/20 transition-colors"
                >
                  <EyeOff className="w-4 h-4" /> Ver Pendientes (
                  {pendientes.toLocaleString()})
                </button>
                {rutaReporte && (
                  <button
                    onClick={() => downloadReport(rutaReporte)}
                    className="gradient-primary text-primary-foreground px-6 py-3 rounded-full text-sm font-medium inline-flex items-center gap-2 shadow-lg hover:-translate-y-0.5 transition-all"
                  >
                    <ExcelIcon className="w-4 h-4" /> Descargar Excel
                  </button>
                )}
                {rutaReporte && (
                  <button
                    onClick={() => downloadReportPdf(rutaReporte)}
                    className="bg-red-600 text-white px-6 py-3 rounded-full text-sm font-medium inline-flex items-center gap-2 shadow-lg hover:bg-red-700 hover:-translate-y-0.5 transition-all"
                  >
                    <PdfIcon className="w-4 h-4" /> Descargar PDF
                  </button>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
