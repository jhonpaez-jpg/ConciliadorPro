import { useApp } from "@/context/AppContext";
import { useStatsForLote } from "@/hooks/useStatsForLote";
import {
  PhaseEmpty,
  PhaseHeroCard,
  PhaseKpi,
  PhaseProgressBar,
  MonthHeader,
} from "@/components/PhaseHero";

export default function SubsetSumSection() {
  const { currentMonthIndex, currentYear } = useApp();
  const { stats, cuenta, isFallback } = useStatsForLote();

  if (!cuenta || !stats) return <PhaseEmpty phase="F2" />;

  const f2 = stats.fases?.F2 ?? {
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
        phase="F2"
        cuenta={cuenta}
        desc={
          <>
            Agrupa registros por{" "}
            <code className="bg-[#fef3c7] text-[#92400e] px-1.5 py-0.5 rounded text-[12px] font-mono">
              n_diario + localidad
            </code>{" "}
            donde la <strong>suma total del grupo es cero</strong>. Si hay más
            de un positivo, subdivide con DP para crear grupos más pequeños. Usa
            candidatos ordenados <strong>descendente</strong> para minimizar
            estados del DP.
          </>
        }
      >
        <div className="grid grid-cols-4 gap-4">
          <PhaseKpi
            value={f2.conciliados.toLocaleString()}
            label="Registros conciliados"
            color="#f59e0b"
          />
          <PhaseKpi
            value={`${f2.pct_sobre_conciliados.toFixed(1)}%`}
            label="% sobre conciliados"
          />
          <PhaseKpi
            value={`${f2.pct_sobre_total.toFixed(1)}%`}
            label="% sobre total"
          />
          <PhaseKpi value="Σ = 0" label="Criterio de grupo" />
        </div>
        <PhaseProgressBar
          pct={f2.pct_sobre_conciliados}
          color="#f59e0b"
          label="F2"
          found={f2.conciliados}
          total={stats.total_conciliados ?? 0}
        />
      </PhaseHeroCard>
    </div>
  );
}
