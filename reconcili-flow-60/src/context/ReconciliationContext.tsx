import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import axios from "axios";
import { toast } from "@/hooks/use-toast";

const API_BASE = "/api";

export interface ReconciliationConfig {
  f2Timeout: number;
  f3Timeout: number;
  f4Timeout: number;
  maxDepth: number;
}

const DEFAULT_CONFIG: ReconciliationConfig = {
  f2Timeout: 2, f3Timeout: 10, f4Timeout: 30, maxDepth: 5,
};

const CONFIG_KEY = "conciliador_config_v1";

function loadConfig(): ReconciliationConfig {
  try {
    const raw = localStorage.getItem(CONFIG_KEY);
    return raw ? { ...DEFAULT_CONFIG, ...JSON.parse(raw) } : DEFAULT_CONFIG;
  } catch { return DEFAULT_CONFIG; }
}

function saveConfig(c: ReconciliationConfig) {
  try { localStorage.setItem(CONFIG_KEY, JSON.stringify(c)); } catch {}
}

export interface ReconciliationResult {
  status: string;
  cuenta_procesada: string;
  total_leido: number;
  conciliados: number;
  pendientes: number;
  tasa_conciliacion?: number;
  ruta_reporte: string;
  periodo?: string;
  mes?: number;
  anio?: number;
}

export interface ScheduledEntry {
  id: number;
  fecha: string;
  hora: string;
  archivo: string;
  estado: "PENDIENTE" | "EJECUTANDO" | "COMPLETADO" | "ERROR" | "CANCELADO";
  creado_en: string;
  ejecutado_en?: string;
}

export interface HistoryEntry {
  id?: number;
  date: string;
  cuenta: string;
  total: number;
  conciliados: number;
  pendientes: number;
  efectividad: string;
  ruta_reporte: string;
  periodo?: string;
  mes?: number;
  anio?: number;
  tasa?: number;
  id_lote?: number;
}

export type ProcessState = "idle" | "processing" | "success" | "error";

function clamp(val: number, min: number, max: number) {
  return Math.min(Math.max(val, min), max);
}

function parsePeriodo(periodo?: string): { mes: number; anio: number } | null {
  if (!periodo) return null;
  const m = periodo.match(/(\d{4})\/(\d{3})/);
  return m ? { mes: parseInt(m[2]) - 1, anio: parseInt(m[1]) } : null;
}

async function pollEstado(onProgress: (msg: string) => void, signal: { cancelled: boolean }): Promise<any> {
  const MAX_WAIT = 3_600_000;
  const start = Date.now();
  while (Date.now() - start < MAX_WAIT) {
    if (signal.cancelled) throw new Error("CANCELLED");
    await new Promise(r => setTimeout(r, 5000));
    if (signal.cancelled) throw new Error("CANCELLED");
    try {
      const { data } = await axios.get(`${API_BASE}/estado/`, { timeout: 15_000 });
      onProgress(data.mensaje || "Procesando...");
      if (data.fase === "listo") return data;
      if (data.fase === "cancelado") throw new Error("CANCELLED");
      if (data.fase === "error") throw new Error(data.mensaje || "Error en servidor");
    } catch (e: any) {
      if (e.message === "CANCELLED") throw e;
      if (e.message?.includes("Error en servidor")) throw e;
    }
  }
  throw new Error("Tiempo máximo de espera excedido. Recarga la página para ver los resultados.");
}

interface ReconciliationContextType {
  state: ProcessState;
  result: ReconciliationResult | null;
  file: File | null;
  errorMessage: string | null;
  progressMessage: string;
  history: HistoryEntry[];
  scheduled: ScheduledEntry[];
  config: ReconciliationConfig;
  setFile: (file: File | null) => void;
  setConfig: (c: ReconciliationConfig) => void;
  uploadAndReconcile: (file: File, config?: ReconciliationConfig) => Promise<void>;
  scheduleReconciliation: (file: File, fecha: string, hora: string, config?: ReconciliationConfig) => Promise<void>;
  cancelScheduled: (id: number) => Promise<void>;
  cancelReconciliation: () => Promise<void>;
  downloadReport: (rutaReporte: string) => Promise<void>;
  downloadReportPdf: (rutaReporte: string) => Promise<void>;
  reset: () => void;
  getHistoryByMonth: (mes: number, anio: number) => HistoryEntry[];
  refreshHistorial: () => Promise<void>;
}

const ReconciliationContext = createContext<ReconciliationContextType | null>(null);

export const useReconciliation = () => {
  const ctx = useContext(ReconciliationContext);
  if (!ctx) throw new Error("useReconciliation must be used within ReconciliationProvider");
  return ctx;
};

export function ReconciliationProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ProcessState>("idle");
  const [result, setResult] = useState<ReconciliationResult | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [progressMessage, setProgressMessage] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [scheduled, setScheduled] = useState<ScheduledEntry[]>([]);
  const [config, setConfigState] = useState<ReconciliationConfig>(loadConfig());
  // Señal de cancelación compartida con el loop de polling
  const cancelSignal = { cancelled: false };

  const setConfig = (c: ReconciliationConfig) => {
    setConfigState(c);
    saveConfig(c);
  };

  // Fuente de verdad: siempre el backend
  const fetchHistorialFromBackend = async () => {
    try {
      const { data } = await axios.get(`${API_BASE}/historial/`, { timeout: 10_000 });
      const entries: HistoryEntry[] = (data.historial ?? []).map((item: any) => ({
        id:           item.id,
        date:         item.fecha || "",
        cuenta:       item.cuenta,
        total:        item.total,
        conciliados:  item.conciliados,
        pendientes:   item.pendientes,
        efectividad:  item.efectividad,
        tasa:         item.tasa,
        ruta_reporte: item.ruta_reporte,
        periodo:      item.periodo,
        mes:          item.mes,
        anio:         item.anio,
        id_lote:      item.id_lote,
      }));
      setHistory(entries);
    } catch {
      // Backend no disponible — mantener estado actual
    }
  };

  // Cargar historial al montar
  useEffect(() => {
    fetchHistorialFromBackend();
    fetchScheduledFromBackend();
    // Verificar si hay un proceso activo en el backend al recargar
    _checkActiveProcess();
  }, []);

  const _checkActiveProcess = async () => {
    try {
      const { data } = await axios.get(`${API_BASE}/estado/`, { timeout: 5_000 });
      const faseActiva = ["cargando", "procesando", "iniciando"];
      if (faseActiva.includes(data.fase)) {
        // Hay un proceso corriendo — retomar el polling
        setState("processing");
        setProgressMessage(data.mensaje || "Procesando...");
        // Reanudar el loop de polling con la señal actual
        cancelSignal.cancelled = false;
        pollEstado((msg) => setProgressMessage(msg), cancelSignal)
          .then((result) => {
            const periodoInfo = parsePeriodo(result.periodo);
            const total = (result.conciliados ?? 0) + (result.pendientes ?? 0);
            const tasa  = result.tasa ?? (total > 0 ? ((result.conciliados ?? 0) / total) * 100 : 0);
            setResult({
              status:            "success",
              cuenta_procesada:  result.cuenta ?? "—",
              total_leido:       total,
              conciliados:       result.conciliados ?? 0,
              pendientes:        result.pendientes  ?? 0,
              tasa_conciliacion: tasa,
              ruta_reporte:      result.reporte ?? "",
              periodo:           result.periodo,
              mes:               periodoInfo?.mes,
              anio:              periodoInfo?.anio,
            });
            setState("success");
            setProgressMessage("");
            fetchHistorialFromBackend();
          })
          .catch((e) => {
            if (e.message === "CANCELLED") {
              setState("idle");
            } else {
              setState("error");
              setErrorMessage(e.message || "Error al procesar");
            }
            setProgressMessage("");
          });
      }
    } catch { /* backend no disponible */ }
  };

  const fetchScheduledFromBackend = async () => {
    try {
      const { data } = await axios.get(`${API_BASE}/programadas/`, { timeout: 5_000 });
      setScheduled(data.programadas ?? []);
    } catch { /* ignorar */ }
  };

  const getHistoryByMonth = (mes: number, anio: number) =>
    history.filter(h => h.mes === mes && h.anio === anio);

  const uploadAndReconcile = async (fileToUpload: File, config?: ReconciliationConfig) => {
    setState("processing");
    setResult(null);
    setErrorMessage(null);
    setProgressMessage("Subiendo archivo...");

    const formData = new FormData();
    formData.append("file", fileToUpload);

    const params = config
      ? new URLSearchParams({
          f2_timeout: String(clamp(config.f2Timeout, 1, 10)),
          f3_timeout: String(clamp(config.f3Timeout, 5, 30)),
          f4_timeout: String(clamp(config.f4Timeout, 15, 120)),
          max_depth:  String(clamp(config.maxDepth, 2, 10)),
        })
      : new URLSearchParams();

    try {
      await axios.post(`${API_BASE}/upload-and-reconcile/?${params}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 30_000,
      });

      setProgressMessage("Procesando...");
      const data = await pollEstado((msg) => setProgressMessage(msg), cancelSignal);

      const periodoInfo = parsePeriodo(data.periodo);
      const total = (data.conciliados ?? 0) + (data.pendientes ?? 0);
      const tasa  = data.tasa ?? (total > 0 ? ((data.conciliados ?? 0) / total) * 100 : 0);

      const mapped: ReconciliationResult = {
        status:           "success",
        cuenta_procesada: data.cuenta ?? "—",
        total_leido:      total,
        conciliados:      data.conciliados ?? 0,
        pendientes:       data.pendientes  ?? 0,
        tasa_conciliacion: tasa,
        ruta_reporte:     data.reporte ?? "",
        periodo:          data.periodo,
        mes:              periodoInfo?.mes,
        anio:             periodoInfo?.anio,
      };

      setResult(mapped);
      setState("success");
      setProgressMessage("");

      toast({
        title: "✅ Conciliación exitosa",
        description: `Cuenta ${mapped.cuenta_procesada}: ${mapped.conciliados} conciliados de ${total}`,
      });

      // Refrescar historial desde el backend (ya incluye la nueva ejecución)
      await fetchHistorialFromBackend();

    } catch (error: any) {
      setState("error");
      // Si fue cancelación, no mostrar como error
      if (error.message === "CANCELLED") {
        setState("idle");
        setProgressMessage("");
        return;
      }
      const message =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "Error desconocido al procesar la conciliación";
      setErrorMessage(message);
      setProgressMessage("");
      toast({
        title: "Error en conciliación",
        description: message,
        variant: "destructive",
      });
    }
  };

  const scheduleReconciliation = async (
    fileToSchedule: File,
    fecha: string,
    hora: string,
    cfg?: ReconciliationConfig,
  ) => {
    const c = cfg ?? config;
    const formData = new FormData();
    formData.append("file", fileToSchedule);
    const params = new URLSearchParams({
      hora, fecha,
      f2_timeout: String(c.f2Timeout),
      f3_timeout: String(c.f3Timeout),
      f4_timeout: String(c.f4Timeout),
      max_depth:  String(c.maxDepth),
    });
    await axios.post(`${API_BASE}/programar/?${params}`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 30_000,
    });
    await fetchScheduledFromBackend();
    toast({
      title: "✅ Ejecución programada",
      description: `El archivo se procesará el ${fecha} a las ${hora}`,
    });
  };

  const cancelScheduled = async (id: number) => {
    try {
      await axios.delete(`${API_BASE}/programadas/${id}`);
      await fetchScheduledFromBackend();
      toast({ title: "Ejecución cancelada", description: "La ejecución programada fue cancelada." });
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
  };

  const cancelReconciliation = async () => {
    cancelSignal.cancelled = true;
    try { await axios.post(`${API_BASE}/cancelar/`); } catch {}
    setState("idle");
    setProgressMessage("");
    setErrorMessage(null);
  };

  const downloadReport = async (rutaReporte: string) => {
    try {
      const filename = rutaReporte.split("/").pop() || rutaReporte;
      const response = await axios.get(
        `${API_BASE}/download-report/${encodeURIComponent(filename)}`,
        { responseType: "blob" }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      const message = error.response?.data?.detail || "No se pudo descargar el reporte";
      toast({
        title: "Error de descarga",
        description: message,
        variant: "destructive",
      });
    }
  };

  const downloadReportPdf = async (rutaReporte: string) => {
    try {
      const filename = rutaReporte.split("/").pop() || rutaReporte;
      const pdfName  = filename.replace(/\.xlsx?$/, ".pdf");
      const response = await axios.get(
        `${API_BASE}/download-report-pdf/${encodeURIComponent(filename)}`,
        { responseType: "blob" }
      );
      const url = window.URL.createObjectURL(new Blob([response.data], { type: "application/pdf" }));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", pdfName);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      const message = error.response?.data?.detail || "No se pudo generar el PDF";
      toast({ title: "Error PDF", description: message, variant: "destructive" });
    }
  };

  const reset = () => {
    cancelSignal.cancelled = true;
    setState("idle");
    setResult(null);
    setFile(null);
    setErrorMessage(null);
    setProgressMessage("");
  };

  return (
    <ReconciliationContext.Provider
      value={{
        state, result, file, errorMessage, progressMessage, history,
        scheduled, config, setConfig,
        setFile, uploadAndReconcile, scheduleReconciliation, cancelScheduled,
        cancelReconciliation, downloadReport, downloadReportPdf,
        reset, getHistoryByMonth, refreshHistorial: fetchHistorialFromBackend,
      }}
    >
      {children}
    </ReconciliationContext.Provider>
  );
}
