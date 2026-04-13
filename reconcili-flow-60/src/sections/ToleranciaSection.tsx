import { useApp } from "@/context/AppContext";
import { useStatsForLote } from "@/hooks/useStatsForLote";
import { PhaseEmpty, PhaseHeroCard, PhaseKpi, PhaseProgressBar, MonthHeader } from "@/components/PhaseHero";

export default function ToleranciaSection() {
  const { currentMonthIndex, currentYear } = useApp();
  const { stats, cuenta, isFallback } = useStatsForLote();

  if (!cuenta || !stats) return <PhaseEmpty phase="F3" />;

  const f3 = stats.fases?.F3 ?? { conciliados: 0, pct_sobre_conciliados: 0, pct_sobre_total: 0 };

  return (
    <div className="space-y-4">
      <MonthHeader monthIndex={currentMonthIndex} year={currentYear} isFallback={isFallback} />
      <PhaseHeroCard
        phase="F3"
        cuenta={cuenta}
        desc={
          <>
            Captura grupos por{" "}
            <code className="bg-[#ede9fe] text-[#5b21b6] px-1.5 py-0.5 rounded text-[12px] font-mono">n_diario + localidad</code>{" "}
            cuya suma no es exactamente cero sino dentro de <strong>±5 centavos</strong>.
            Cubre diferencias de redondeo entre sistemas contables. Históricamente vacía en los datos reales (buena señal de calidad).
          </>
        }
      >
        <div className="grid grid-cols-4 gap-4">
          <PhaseKpi value={f3.conciliados.toLocaleString()} label="Registros conciliados" color="#8b5cf6" />
          <PhaseKpi value={`${f3.pct_sobre_conciliados.toFixed(1)}%`} label="% sobre conciliados" />
          <PhaseKpi value={`${f3.pct_sobre_total.toFixed(1)}%`} label="% sobre total" />
          <PhaseKpi value="±5 cts" label="Tolerancia" />
        </div>
        <PhaseProgressBar
          pct={f3.pct_sobre_conciliados}
          color="#8b5cf6"
          label="F3"
          found={f3.conciliados}
          total={stats.total_conciliados ?? 0}
        />
      </PhaseHeroCard>
    </div>
  );
}
