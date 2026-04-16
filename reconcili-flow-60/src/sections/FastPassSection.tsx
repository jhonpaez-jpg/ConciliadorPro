import { useApp } from "@/context/AppContext";
import { useStatsForLote } from "@/hooks/useStatsForLote";
import {
  PhaseEmpty,
  PhaseHeroCard,
  PhaseKpi,
  PhaseProgressBar,
  MonthHeader,
} from "@/components/PhaseHero";

export default function FastPassSection() {
  const { currentMonthIndex, currentYear } = useApp();
  const { stats, cuenta, isFallback } = useStatsForLote();

  if (!cuenta || !stats) return <PhaseEmpty phase="F1" />;

  const f1 = stats.fases?.F1 ?? {
    conciliados: 0,
    pct_sobre_conciliados: 0,
    pct_sobre_total: 0,
  };

  return (
    <div className="space-y-4">
      <MonthHeader
        monthIndex={currentMonthIndex}
        year={currentYear}
        isFallback={isFallback}
      />
      <PhaseHeroCard
        phase="F1"
        cuenta={cuenta}
        desc={
          <>
            Empareja registros con <strong>monto exactamente opuesto</strong>{" "}
            que comparten el mismo{" "}
            <code className="bg-[#d1fae5] text-[#065f46] px-1.5 py-0.5 rounded text-[12px] font-mono">
              n_diario
            </code>{" "}
            y{" "}
            <code className="bg-[#d1fae5] text-[#065f46] px-1.5 py-0.5 rounded text-[12px] font-mono">
              localidad
            </code>
            . Es la fase más rápida — un join en Polars de O(n). Se ejecuta
            primero para reducir el universo de las fases siguientes.
          </>
        }
      >
        <div className="grid grid-cols-4 gap-4">
          <PhaseKpi
            value={f1.conciliados.toLocaleString()}
            label="Registros conciliados"
            color="#10b981"
          />
          <PhaseKpi
            value={`${f1.pct_sobre_conciliados.toFixed(1)}%`}
            label="% sobre conciliados"
          />
          <PhaseKpi
            value={`${f1.pct_sobre_total.toFixed(1)}%`}
            label="% sobre total"
          />
          <PhaseKpi value="<1ms" label="Tiempo por registro" />
        </div>
        <PhaseProgressBar
          pct={f1.pct_sobre_conciliados}
          color="#10b981"
          label="F1"
          found={f1.conciliados}
          total={stats.total_conciliados ?? 0}
        />
      </PhaseHeroCard>
    </div>
  );
}
