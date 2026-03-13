import { ChevronLeft, ChevronRight, CheckCircle, Clock, Database, Calendar } from "lucide-react";
import { useApp, getMonthName } from "@/context/AppContext";
import { useReconciliation } from "@/context/ReconciliationContext";

export default function MonthlyNav() {
  const { currentMonthIndex, currentYear, nextMonth, prevMonth, isCurrentMonth } = useApp();
  const { history } = useReconciliation();
  const ultimo = history[0] ?? null;
  const total = ultimo?.total ?? 0;
  const conciliados = ultimo?.conciliados ?? 0;
  const efectividad = total > 0 ? ((conciliados / total) * 100).toFixed(0) + "%" : "—";
  const fechaHoy = new Date().toLocaleDateString("es-CO");

  return (
    <header className="bg-header-bg px-8 py-4 flex justify-between items-center flex-shrink-0 border-b border-sidebar-border">
      <div className="flex items-center gap-5 bg-sidebar-border/30 px-4 py-2 rounded-full">
        <button onClick={prevMonth} className="w-9 h-9 rounded-full flex items-center justify-center text-sidebar-muted hover:bg-sidebar-border/50 hover:text-sidebar-fg transition-colors">
          <ChevronLeft className="w-5 h-5" />
        </button>
        <span className="text-sidebar-fg font-medium text-lg min-w-[200px] text-center flex items-center justify-center gap-2">
          <Calendar className="w-4 h-4 text-primary" />
          {getMonthName(currentMonthIndex)} {currentYear}
        </span>
        <button
          onClick={nextMonth}
          disabled={isCurrentMonth()}
          className={`w-9 h-9 rounded-full flex items-center justify-center transition-colors ${
            isCurrentMonth()
              ? "text-sidebar-muted/30 cursor-not-allowed"
              : "text-sidebar-muted hover:bg-sidebar-border/50 hover:text-sidebar-fg"
          }`}
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      <div className="flex gap-6">
        <div className="flex items-center gap-2 text-sidebar-muted text-sm">
          <CheckCircle className="w-4 h-4 text-primary" />
          <span>{efectividad} conciliado</span>
        </div>
        <div className="flex items-center gap-2 text-sidebar-muted text-sm">
          <Clock className="w-4 h-4 text-primary" />
          <span>{fechaHoy}</span>
        </div>
        <div className="flex items-center gap-2 text-sidebar-muted text-sm">
          <Database className="w-4 h-4 text-primary" />
          <span>{total > 0 ? total.toLocaleString() + " reg." : "— reg."}</span>
        </div>
      </div>
    </header>
  );
}
