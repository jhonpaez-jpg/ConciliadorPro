import { useState } from "react";
import { cn } from "@/lib/utils";

interface ConfigItem {
  title: string;
  desc: string;
  type: "number" | "toggle";
  value: number | boolean;
  unit?: string;
  min?: number;
  max?: number;
}

const timeoutItems: ConfigItem[] = [
  { title: "Fase 2 - Subset Sum", desc: "Tiempo máximo por registro en búsqueda 1:N", type: "number", value: 2, unit: "segundos", min: 1, max: 10 },
  { title: "Fase 3 - Media", desc: "Tiempo máximo para búsqueda media", type: "number", value: 10, unit: "segundos", min: 5, max: 30 },
  { title: "Fase 4 - Profunda", desc: "Tiempo máximo para búsqueda nocturna", type: "number", value: 30, unit: "segundos", min: 15, max: 120 },
];

const limitItems: ConfigItem[] = [
  { title: "Profundidad máxima F2", desc: "Número máximo de elementos en combinación", type: "number", value: 5, min: 2, max: 10 },
  { title: "Profundidad máxima F3", desc: "Para búsqueda media", type: "number", value: 8, min: 3, max: 15 },
];

const toggleItems = [
  { title: "Modo estricto de cuentas", desc: "No cruzar valores entre diferentes cuentas", active: true },
  { title: "Notificaciones automáticas", desc: "Alertar cuando termine cada fase", active: false },
  { title: "Guardar logs detallados", desc: "Mantener trazabilidad por 30 días", active: true },
];

export default function ConfiguracionSection() {
  const [toggles, setToggles] = useState(toggleItems.map(t => t.active));

  return (
    <div className="bg-card rounded-2xl p-6 shadow-card space-y-8">
      {/* Timeouts */}
      <div>
        <h4 className="text-sm font-semibold text-card-foreground mb-4 pb-2 border-b border-border">Timeouts por Fase</h4>
        <div className="space-y-2">
          {timeoutItems.map((item, i) => (
            <div key={i} className="flex justify-between items-center p-4 bg-muted/50 rounded-2xl">
              <div>
                <h4 className="text-sm font-medium text-card-foreground">{item.title}</h4>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
              <div className="flex items-center gap-4">
                <input type="number" defaultValue={item.value as number} min={item.min} max={item.max}
                  className="w-20 px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary/30" />
                {item.unit && <span className="text-sm text-muted-foreground">{item.unit}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Limits */}
      <div>
        <h4 className="text-sm font-semibold text-card-foreground mb-4 pb-2 border-b border-border">Límites de Combinación</h4>
        <div className="space-y-2">
          {limitItems.map((item, i) => (
            <div key={i} className="flex justify-between items-center p-4 bg-muted/50 rounded-2xl">
              <div>
                <h4 className="text-sm font-medium text-card-foreground">{item.title}</h4>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
              <input type="number" defaultValue={item.value as number} min={item.min} max={item.max}
                className="w-20 px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary/30" />
            </div>
          ))}
        </div>
      </div>

      {/* Toggles */}
      <div>
        <h4 className="text-sm font-semibold text-card-foreground mb-4 pb-2 border-b border-border">Opciones Generales</h4>
        <div className="space-y-2">
          {toggleItems.map((item, i) => (
            <div key={i} className="flex justify-between items-center p-4 bg-muted/50 rounded-2xl">
              <div>
                <h4 className="text-sm font-medium text-card-foreground">{item.title}</h4>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
              <button
                onClick={() => setToggles(prev => { const n = [...prev]; n[i] = !n[i]; return n; })}
                className={cn(
                  "w-11 h-6 rounded-full relative transition-colors",
                  toggles[i] ? "bg-primary" : "bg-border"
                )}
              >
                <div className={cn(
                  "w-5 h-5 rounded-full bg-card absolute top-0.5 transition-all",
                  toggles[i] ? "right-0.5" : "right-[22px]"
                )} />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-4">
        <button className="gradient-primary text-primary-foreground px-6 py-3 rounded-full text-sm font-medium shadow-lg hover:-translate-y-0.5 transition-all">
          Guardar Cambios
        </button>
        <button className="bg-card text-muted-foreground border border-border px-5 py-2.5 rounded-full text-sm hover:border-primary transition-colors">
          Restaurar Valores
        </button>
      </div>
    </div>
  );
}
