import { useState, useEffect } from "react";
import axios from "axios";
import { useReconciliation } from "@/context/ReconciliationContext";
import { useApp } from "@/context/AppContext";

export interface FaseStats {
  conciliados: number;
  pct_sobre_conciliados: number;
  pct_sobre_total: number;
}

export interface LoteStats {
  cuenta: string;
  id_lote: number;
  total_global: number;
  total_conciliados: number;
  pendientes: number;
  pct_conciliados: number;
  pct_pendientes: number;
  fases: Record<string, FaseStats>;
}

/**
 * Obtiene las estadísticas por fase para el lote correspondiente al mes/año
 * seleccionado en el navegador. Si no hay datos del mes, usa el último lote disponible.
 * Siempre filtra por id_lote — garantiza datos del mes correcto.
 */
export function useStatsForLote() {
  const { history, getHistoryByMonth } = useReconciliation();
  const { currentMonthIndex, currentYear } = useApp();
  const [stats, setStats] = useState<LoteStats | null>(null);
  const [loading, setLoading] = useState(false);

  const historialMes = getHistoryByMonth(currentMonthIndex, currentYear);
  // Priorizar el mes seleccionado; si no hay, usar el último disponible
  const entrada = historialMes[0] ?? history[0] ?? null;
  const cuenta   = entrada?.cuenta   ?? null;
  const id_lote  = entrada?.id_lote  ?? null;
  const isFallback = historialMes.length === 0 && history.length > 0;

  useEffect(() => {
    if (!cuenta || id_lote == null) {
      setStats(null);
      return;
    }
    setLoading(true);
    axios
      .get("/api/stats-por-fase/", { params: { cuenta, id_lote } })
      .then(({ data }) => setStats(data))
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, [cuenta, id_lote]);

  return { stats, loading, cuenta, id_lote, isFallback, historialMes };
}
