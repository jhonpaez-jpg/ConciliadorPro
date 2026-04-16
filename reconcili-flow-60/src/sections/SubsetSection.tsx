import { useApp } from "@/context/AppContext";
import { useStatsForLote } from "@/hooks/useStatsForLote";
import {
  PhaseEmpty,
  PhaseHeroCard,
  PhaseKpi,
  PhaseProgressBar,
  MonthHeader,
} from "@/components/PhaseHero";

export default function SubsetSection() {
  const { currentMonthIndex, currentYear } = useApp();
  const { stats, cuenta, isFallback } = useStatsForLote();

  if (!cuenta || !stats) return <PhaseEmpty phase="F6" />;

  const f6 = stats.fases?.F6 ?? {
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
        phase="F6"
        cuenta={cuenta}
        desc={
          <>
            Atiende negativos de valor{" "}
            <code className="bg-[#ffedd5] text-[#c2410c] px-1.5 py-0.5 rounded text-[12px] font-mono">
              &gt;$500K COP
            </code>{" "}
            que ningún positivo individual puede cubrir. Busca subconjuntos de
            positivos cuya suma equivale al valor absoluto del negativo. Se
            ejecuta <strong>antes de F7</strong> para que los positivos más
            adecuados estén disponibles.
          </>
        }
      >
        <div className="grid grid-cols-4 gap-4">
          <PhaseKpi
            value={f6.conciliados.toLocaleString()}
            label="Registros conciliados"
            color="#f97316"
          />
          <PhaseKpi
            value={`${f6.pct_sobre_conciliados.toFixed(1)}%`}
            label="% sobre conciliados"
          />
          <PhaseKpi
            value={`${f6.pct_sobre_total.toFixed(1)}%`}
            label="% sobre total"
          />
          <PhaseKpi value="N→1" label="Patrón (N pos, 1 neg)" />
        </div>
        <PhaseProgressBar
          pct={f6.pct_sobre_conciliados}
          color="#f97316"
          label="F6"
          found={f6.conciliados}
          total={stats.total_conciliados ?? 0}
        />
      </PhaseHeroCard>
    </div>
  );
}
