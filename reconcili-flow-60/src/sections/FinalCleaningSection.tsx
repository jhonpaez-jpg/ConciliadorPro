import { useApp } from "@/context/AppContext";
import { useStatsForLote } from "@/hooks/useStatsForLote";
import { PhaseEmpty, PhaseHeroCard, PhaseKpi, PhaseProgressBar, MonthHeader, PHASE_CONFIG } from "@/components/PhaseHero";

export default function FinalCleaningSection() {
  const { currentMonthIndex, currentYear } = useApp();
  const { stats, cuenta, isFallback } = useStatsForLote();

  if (!cuenta || !stats) return <PhaseEmpty phase="F7" />;

  const f7  = stats.fases?.F7  ?? { conciliados: 0, pct_sobre_conciliados: 0, pct_sobre_total: 0 };
  const f7b = stats.fases?.F7b ?? { conciliados: 0, pct_sobre_conciliados: 0, pct_sobre_total: 0 };
  const totalFinal = f7.conciliados + f7b.conciliados;
  const pctTotal   = (stats.total_conciliados ?? 0) > 0
    ? (totalFinal / stats.total_conciliados) * 100 : 0;
  const pctGlobal  = (stats.total_global ?? 0) > 0
    ? (totalFinal / stats.total_global) * 100 : 0;

  return (
    <div className="space-y-4">
      <MonthHeader monthIndex={currentMonthIndex} year={currentYear} isFallback={isFallback} />
      <PhaseHeroCard
        phase="F7"
        cuenta={cuenta}
        desc={
          <>
            La fase más importante del motor. Un registro SIF82 positivo grande absorbe múltiples registros TES82 negativos pequeños.
            Positivos iterados en orden <strong>ascendente</strong> — los pequeños encuentran solución rápido y dejan negativos grandes
            disponibles para los positivos más grandes.{" "}
            <strong>F7b</strong> limpia los positivos restantes con DP exacto sin escala.
          </>
        }
      >
        {/* KPIs combinados F7 + F7b */}
        <div className="grid grid-cols-4 gap-4">
          <PhaseKpi value={totalFinal.toLocaleString()} label="Total F7 + F7b" color="#06b6d4" />
          <PhaseKpi value={`${pctTotal.toFixed(1)}%`} label="% sobre conciliados" />
          <PhaseKpi value={`${pctGlobal.toFixed(1)}%`} label="% sobre total" />
          <PhaseKpi value="<1s" label="Tiempo F7b (v4)" color="#84cc16" />
        </div>

        <PhaseProgressBar
          pct={pctTotal}
          color="#06b6d4"
          label="F7 + F7b"
          found={totalFinal}
          total={stats.total_conciliados ?? 0}
        />

        {/* Desglose F7 / F7b */}
        <div className="space-y-3">
          <p className="text-sm font-semibold text-[#1e293b]">Desglose por sub-fase</p>

          {/* F7 */}
          <div className="bg-[#f8fafc] rounded-2xl p-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold" style={{ color: PHASE_CONFIG.F7.color }}>
                  {PHASE_CONFIG.F7.icon} F7
                </span>
                <span className="text-xs text-[#64748b]">1 positivo → N negativos</span>
              </div>
              <div className="text-right">
                <span className="text-sm font-bold text-[#1e293b]">{f7.conciliados.toLocaleString()}</span>
                <span className="text-xs text-[#64748b] ml-1">({f7.pct_sobre_conciliados.toFixed(1)}%)</span>
              </div>
            </div>
            <div className="w-full bg-[#e2e8f0] rounded-full h-2">
              <div className="h-2 rounded-full transition-all"
                   style={{ width: `${Math.min(f7.pct_sobre_conciliados, 100)}%`, background: "#06b6d4" }} />
            </div>
          </div>

          {/* F7b */}
          <div className="bg-[#f8fafc] rounded-2xl p-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold" style={{ color: PHASE_CONFIG.F7b.color }}>
                  {PHASE_CONFIG.F7b.icon} F7b
                </span>
                <span className="text-xs text-[#64748b]">Limpieza final positivos restantes</span>
              </div>
              <div className="text-right">
                <span className="text-sm font-bold text-[#1e293b]">{f7b.conciliados.toLocaleString()}</span>
                <span className="text-xs text-[#64748b] ml-1">({f7b.pct_sobre_conciliados.toFixed(1)}%)</span>
              </div>
            </div>
            <div className="w-full bg-[#e2e8f0] rounded-full h-2">
              <div className="h-2 rounded-full transition-all"
                   style={{ width: `${Math.min(f7b.pct_sobre_conciliados, 100)}%`, background: "#84cc16" }} />
            </div>
          </div>
        </div>
      </PhaseHeroCard>
    </div>
  );
}
