import { useState, useEffect } from "react";
import axios from "axios";
import StatCard from "@/components/StatCard";
import { FileSpreadsheet, Cpu, CheckCircle, Calendar } from "lucide-react";
import { useReconciliation } from "@/context/ReconciliationContext";
import { useApp, getMonthName } from "@/context/AppContext";

export default function MontoPuroSection() {
  const { history, getHistoryByMonth } = useReconciliation();
  const { currentMonthIndex, currentYear } = useApp();
  const [stats, setStats] = useState<any>(null);

  const mesLabel = `${getMonthName(currentMonthIndex)} ${currentYear}`;
  const historialMes = getHistoryByMonth(currentMonthIndex, currentYear);
  const cuentaFuente = historialMes[0] ?? history[0] ?? null;
  const cuenta = cuentaFuente?.cuenta ?? null;

  useEffect(() => {
    if (!cuenta) return;
    axios.get("/api/stats-por-fase/", { params: { cuenta } })
      .then(({ data }) => setStats(data))
      .catch(() => setStats(null));
  }, [cuenta]);

  if (!cuenta || !stats) {
    return (
      <div className="bg-card rounded-2xl p-12 shadow-card text-center">
        <FileSpreadsheet className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-card-foreground mb-2">F5: Monto Puro Global</h3>
        <p className="text-muted-foreground text-sm">Ejecuta una conciliación para ver resultados de esta fase.</p>
      </div>
    );
  }

  const f5 = stats.fases?.F5 ?? { conciliados: 0, pct_sobre_conciliados: 0, pct_sobre_total: 0 };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-2 text-muted-foreground text-sm">
          <Calendar className="w-4 h-4 text-primary" />
          <span>Datos de <strong className="text-card-foreground">{mesLabel}</strong></span>
        </div>
        {!historialMes.length && history.length > 0 && (
          <span className="px-3 py-1 rounded-full text-xs font-medium bg-warning/10 text-warning">
            ⚠ Última conciliación disponible
          </span>
        )}
      </div>
      <div className="bg-card rounded-2xl p-6 shadow-card space-y-6">
        <div>
          <h3 className="text-lg font-semibold text-card-foreground mb-2">F5: Monto Puro Global</h3>
          <p className="text-muted-foreground text-sm">Parejas exactas solo por monto, sin localidad ni número de diario — Cuenta: {cuenta}</p>
        </div>
        <div className="grid grid-cols-3 gap-5">
          <StatCard title="Conciliados F5" value={f5.conciliados.toLocaleString()} icon={Cpu} />
          <StatCard title="% sobre conciliados" value={`${f5.pct_sobre_conciliados.toFixed(1)}%`} icon={CheckCircle} />
          <StatCard title="% sobre total" value={`${f5.pct_sobre_total.toFixed(1)}%`} icon={CheckCircle} />
        </div>
        <div className="bg-muted/50 rounded-2xl p-4">
          <p className="text-xs text-muted-foreground mb-2">Contribución de F5 al total conciliado</p>
          <div className="w-full bg-border rounded-full h-3">
            <div className="bg-primary h-3 rounded-full transition-all" style={{ width: `${Math.min(f5.pct_sobre_conciliados, 100)}%` }} />
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            F5 encontró {f5.conciliados.toLocaleString()} de {(stats.total_conciliados ?? 0).toLocaleString()} conciliados totales
          </p>
        </div>
      </div>
    </div>
  );
}
