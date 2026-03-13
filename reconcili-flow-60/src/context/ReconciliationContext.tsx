import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import axios from "axios";
import { toast } from "@/hooks/use-toast";

const API_BASE = "/api";
const STORAGE_KEY = "reconciliacion_v1";

export interface ReconciliationConfig {
  f2Timeout: number;
  f3Timeout: number;
  f4Timeout: number;
  maxDepth: number;
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

export interface HistoryEntry {
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
}

export type ProcessState = "idle" | "processing" | "success" | "error";

interface PersistedData {
  result: ReconciliationResult | null;
  history: HistoryEntry[];
}

function loadPersisted(): PersistedData {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : { result: null, history: [] };
  } catch {
    return { result: null, history: [] };
  }
}

function savePersisted(data: PersistedData) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {}
}

function clamp(val: number, min: number, max: number) {
  return Math.min(Math.max(val, min), max);
}

function parsePeriodo(periodo?: string): { mes: number; anio: number } | null {
  if (!periodo) return null;
  const m = periodo.match(/(\d{4})\/(\d{3})/);
  return m ? { mes: parseInt(m[2]) - 1, anio: parseInt(m[1]) } : null;
}

async function pollEstado(onProgress: (msg: string) => void): Promise<any> {
  const MAX_WAIT = 3_600_000;
  const start = Date.now();
  while (Date.now() - start < MAX_WAIT) {
    await new Promise(r => setTimeout(r, 5000));
    try {
      const { data } = await axios.get(`${API_BASE}/estado/`, { timeout: 15_000 });
      onProgress(data.mensaje || "Procesando...");
      if (data.fase === "listo") return data;
      if (data.fase === "error") throw new Error(data.mensaje || "Error en servidor");
    } catch (e: any) {
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
  setFile: (file: File | null) => void;
  uploadAndReconcile: (file: File, config?: ReconciliationConfig) => Promise<void>;
  downloadReport: (rutaReporte: string) => Promise<void>;
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
  const persisted = loadPersisted();
  const [state, setState] = useState<ProcessState>("idle");
  const [result, setResult] = useState<ReconciliationResult | null>(persisted.result);
  const [file, setFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [progressMessage, setProgressMessage] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>(persisted.history);

  useEffect(() => {
    savePersisted({ result, history });
  }, [result, history]);

  // Fetch historial from backend on mount
  const fetchHistorialFromBackend = async () => {
    try {
      const { data } = await axios.get(`${API_BASE}/historial/`, { timeout: 10_000 });
      const backendHistory: HistoryEntry[] = (data.historial ?? []).map((item: any) => ({
        date: item.fecha || new Date().toLocaleDateString("es-CO"),
        cuenta: item.cuenta,
        total: item.total,
        conciliados: item.conciliados,
        pendientes: item.pendientes,
        efectividad: item.efectividad,
        tasa: item.tasa,
        ruta_reporte: item.ruta_reporte,
        periodo: item.periodo,
        mes: item.mes,
        anio: item.anio,
      }));
      if (backendHistory.length > 0) {
        setHistory(backendHistory);
        savePersisted({ result, history: backendHistory });
      }
    } catch {
      // Backend unavailable, use localStorage fallback
    }
  };

  useEffect(() => {
    fetchHistorialFromBackend();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
          max_depth: String(clamp(config.maxDepth, 2, 10)),
        })
      : new URLSearchParams();

    try {
      await axios.post(`${API_BASE}/upload-and-reconcile/?${params}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 30_000,
      });

      setProgressMessage("Procesando...");
      const data = await pollEstado((msg) => setProgressMessage(msg));

      const periodoInfo = parsePeriodo(data.periodo);
      const total = (data.conciliados ?? 0) + (data.pendientes ?? 0);
      const tasa = data.tasa ?? (total > 0 ? ((data.conciliados ?? 0) / total) * 100 : 0);

      const mapped: ReconciliationResult = {
        status: "success",
        cuenta_procesada: data.cuenta ?? "—",
        total_leido: total,
        conciliados: data.conciliados ?? 0,
        pendientes: data.pendientes ?? 0,
        tasa_conciliacion: tasa,
        ruta_reporte: data.reporte ?? "",
        periodo: data.periodo,
        mes: periodoInfo?.mes,
        anio: periodoInfo?.anio,
      };

      setResult(mapped);
      setState("success");
      setProgressMessage("");

      const efectividad = `${tasa.toFixed(1)}%`;
      setHistory(prev => [
        {
          date: new Date().toLocaleDateString("es-CO"),
          cuenta: mapped.cuenta_procesada,
          total,
          conciliados: mapped.conciliados,
          pendientes: mapped.pendientes,
          efectividad,
          tasa,
          ruta_reporte: mapped.ruta_reporte,
          periodo: mapped.periodo,
          mes: mapped.mes,
          anio: mapped.anio,
        },
        ...prev,
      ]);

      toast({
        title: "✅ Conciliación exitosa",
        description: `Cuenta ${mapped.cuenta_procesada}: ${mapped.conciliados} conciliados de ${total}`,
      });

      // Refresh from backend after success
      await fetchHistorialFromBackend();
    } catch (error: any) {
      setState("error");
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

  const reset = () => {
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
        setFile, uploadAndReconcile, downloadReport, reset, getHistoryByMonth,
        refreshHistorial: fetchHistorialFromBackend,
      }}
    >
      {children}
    </ReconciliationContext.Provider>
  );
}
