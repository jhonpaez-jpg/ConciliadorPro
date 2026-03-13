import {
  BarChart3, Zap, Layers, Cpu, Clock, Moon,
  Play, History, Settings, FileOutput, PieChart
} from "lucide-react";
import { useApp, SectionId } from "@/context/AppContext";
import { cn } from "@/lib/utils";

interface MenuItem {
  id: SectionId;
  label: string;
  icon: React.ElementType;
  group: string;
}

const menuItems: MenuItem[] = [
  { id: "dashboard", label: "Dashboard", icon: PieChart, group: "PRINCIPAL" },
  { id: "ejecutar", label: "Ejecutar Conciliación", icon: Play, group: "PRINCIPAL" },
  { id: "historial", label: "Historial", icon: History, group: "PRINCIPAL" },
  { id: "fastpass", label: "Fast-Pass (F1)", icon: Zap, group: "CONCILIACIÓN" },
  { id: "subsetsum", label: "Subset Sum (F2)", icon: Layers, group: "CONCILIACIÓN" },
  { id: "tolerancia", label: "Tolerancia F3 (±5 cts)", icon: Clock, group: "CONCILIACIÓN" },
  { id: "localidad", label: "Localidad F4", icon: Moon, group: "CONCILIACIÓN" },
  { id: "montopuro", label: "Monto Puro F5", icon: Cpu, group: "CONCILIACIÓN" },
  { id: "configuracion", label: "Ajustes", icon: Settings, group: "CONFIGURACIÓN" },
  { id: "reportes", label: "Reportes", icon: FileOutput, group: "CONFIGURACIÓN" },
];

export default function AppSidebar() {
  const { activeSection, setActiveSection } = useApp();

  const groups = [...new Set(menuItems.map(i => i.group))];

  return (
    <aside className="w-[280px] bg-sidebar-bg flex flex-col flex-shrink-0 h-full overflow-hidden">
      <div className="px-6 py-6 border-b border-sidebar-border flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl gradient-primary flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-sidebar-fg">Conciliador Pro</h2>
            <p className="text-xs text-sidebar-muted">Motor Automático</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto sidebar-scrollbar p-6 space-y-6">
        {groups.map(group => (
          <div key={group}>
            <p className="text-[11px] uppercase tracking-widest text-sidebar-muted mb-3 font-medium">
              {group}
            </p>
            <div className="space-y-1">
              {menuItems.filter(i => i.group === group).map(item => {
                const isActive = activeSection === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveSection(item.id)}
                    className={cn(
                      "w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all duration-200",
                      isActive
                        ? "bg-primary/20 text-sidebar-fg border-l-[3px] border-primary"
                        : "text-sidebar-muted hover:bg-sidebar-border/30 hover:text-sidebar-fg border-l-[3px] border-transparent"
                    )}
                  >
                    <item.icon className={cn(
                      "w-[18px] h-[18px] flex-shrink-0",
                      isActive ? "text-primary" : "text-sidebar-muted"
                    )} />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
