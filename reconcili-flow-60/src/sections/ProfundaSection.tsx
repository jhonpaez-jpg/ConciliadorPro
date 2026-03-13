import { useState, useEffect } from "react";
import axios from "axios";
import StatCard from "@/components/StatCard";
import { Cpu, CheckCircle, FileSpreadsheet, Clock, Moon, Calendar } from "lucide-react";
import { useReconciliation } from "@/context/ReconciliationContext";
import { useApp, getMonthName } from "@/context/AppContext";

export default function ProfundaSection() {
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
        <h3 className="text-lg font-semibold text-card-foreground mb-2">Resumen Fases Avanzadas (F3–F5)</h3>
        <p className="text-muted-foreground text-sm">Ejecuta una conciliación para ver resultados.</p>
      </div>
    );
  }

  const f3 = stats.fases?.F3 ?? { conciliados: 0, pct_sobre_conciliados: 0, pct_sobre_total: 0 };
  const f4 = stats.fases?.F4 ?? { conciliados: 0, pct_sobre_conciliados: 0, pct_sobre_total: 0 };
  const f5 = stats.fases?.F5 ?? { conciliados: 0, pct_sobre_conciliados: 0, pct_sobre_total: 0 };

  const phases = [
    { key: "F3", label: "Tolerancia ±5 cts", icon: Clock, data: f3, color: "bg-warning" },
    { key: "F4", label: "Monto + Localidad", icon: Moon, data: f4, color: "bg-accent-foreground" },
    { key: "F5", label: "Monto Puro Global", icon: Cpu, data: f5, color: "bg-primary" },
  ];

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
          <h3 className="text-lg font-semibold text-card-foreground mb-2">Resumen Fases Avanzadas (F3–F5)</h3>
          <p className="text-muted-foreground text-sm">Cuenta: {cuenta}</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {phases.map(({ key, label, icon: Icon, data, color }) => (
            <div key={key} className="bg-muted/50 rounded-2xl p-5 space-y-4">
              <div className="flex items-center gap-2">
                <Icon className="w-4 h-4 text-muted-foreground" />
                <h4 className="font-medium text-card-foreground">{key}: {label}</h4>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <StatCard title="Conciliados" value={data.conciliados.toLocaleString()} icon={CheckCircle} />
                <StatCard title="% total" value={`${data.pct_sobre_total.toFixed(1)}%`} />
              </div>
              <div>
                <div className="w-full bg-border rounded-full h-2">
                  <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${Math.min(data.pct_sobre_conciliados, 100)}%` }} />
                </div>
                <p className="text-[11px] text-muted-foreground mt-1">{data.pct_sobre_conciliados.toFixed(1)}% de conciliados</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
