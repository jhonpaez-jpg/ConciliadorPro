import { useApp } from "@/context/AppContext";
import { useStatsForLote } from "@/hooks/useStatsForLote";
import {
  PhaseEmpty,
  PhaseHeroCard,
  PhaseKpi,
  PhaseProgressBar,
  MonthHeader,
} from "@/components/PhaseHero";

export default function MontoPuroSection() {
  const { currentMonthIndex, currentYear } = useApp();
  const { stats, cuenta, isFallback } = useStatsForLote();

  if (!cuenta || !stats) return <PhaseEmpty phase="F5" />;

  const f5 = stats.fases?.F5 ?? {
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
        phase="F5"
        cuenta={cuenta}
        desc={
          <>
            Fase de <strong>último recurso</strong>. Empareja positivos y
            negativos de <strong>monto exactamente igual</strong> sin ninguna
            restricción geográfica ni de n_diario. Se ejecuta{" "}
            <strong>después de F6/F7/F7b</strong> para no consumir contrapartes
            que esas fases necesitan.
          </>
        }
      >
        <div className="grid grid-cols-4 gap-4">
          <PhaseKpi
            value={f5.conciliados.toLocaleString()}
            label="Registros conciliados"
            color="#ef4444"
          />
          <PhaseKpi
            value={`${f5.pct_sobre_conciliados.toFixed(1)}%`}
            label="% sobre conciliados"
          />
          <PhaseKpi
            value={`${f5.pct_sobre_total.toFixed(1)}%`}
            label="% sobre total"
          />
          <PhaseKpi value="ÚLTIMA" label="Posición en pipeline" />
        </div>
        <PhaseProgressBar
          pct={f5.pct_sobre_conciliados}
          color="#ef4444"
          label="F5"
          found={f5.conciliados}
          total={stats.total_conciliados ?? 0}
        />
      </PhaseHeroCard>
    </div>
  );
}
