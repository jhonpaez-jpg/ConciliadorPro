import { useApp } from "@/context/AppContext";
import { useStatsForLote } from "@/hooks/useStatsForLote";
import { PhaseEmpty, PhaseHeroCard, PhaseKpi, PhaseProgressBar, MonthHeader } from "@/components/PhaseHero";

export default function LocalidadSection() {
  const { currentMonthIndex, currentYear } = useApp();
  const { stats, cuenta, isFallback } = useStatsForLote();

  if (!cuenta || !stats) return <PhaseEmpty phase="F4" />;

  const f4 = stats.fases?.F4 ?? { conciliados: 0, pct_sobre_conciliados: 0, pct_sobre_total: 0 };

  return (
    <div className="space-y-4">
      <MonthHeader monthIndex={currentMonthIndex} year={currentYear} isFallback={isFallback} />
      <PhaseHeroCard
        phase="F4"
        cuenta={cuenta}
        desc={
          <>
            Extiende F1 relajando la restricción de{" "}
            <code className="bg-[#dbeafe] text-[#1d4ed8] px-1.5 py-0.5 rounded text-[12px] font-mono">n_diario</code>.
            {" "}Cruza registros con <strong>mismo monto exacto y misma localidad</strong>, independientemente del número de diario.
            Captura cruces SIF82↔TES82 que comparten localidad pero no n_diario.
          </>
        }
      >
        <div className="grid grid-cols-4 gap-4">
          <PhaseKpi value={f4.conciliados.toLocaleString()} label="Registros conciliados" color="#3b82f6" />
          <PhaseKpi value={`${f4.pct_sobre_conciliados.toFixed(1)}%`} label="% sobre conciliados" />
          <PhaseKpi value={`${f4.pct_sobre_total.toFixed(1)}%`} label="% sobre total" />
          <PhaseKpi value="1:1" label="Patrón" />
        </div>
        <PhaseProgressBar
          pct={f4.pct_sobre_conciliados}
          color="#3b82f6"
          label="F4"
          found={f4.conciliados}
          total={stats.total_conciliados ?? 0}
        />
      </PhaseHeroCard>
    </div>
  );
}
