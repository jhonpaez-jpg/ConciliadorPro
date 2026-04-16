import { useState, useEffect } from "react";
import { Save, RotateCcw, CheckCircle, Bell, BellOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { useReconciliation } from "@/context/ReconciliationContext";
import { requestNotificationPermission } from "@/hooks/useNotifications";

const DEFAULT = { f2Timeout: 2, f3Timeout: 10, f4Timeout: 30, maxDepth: 5 };

const TIMEOUT_FIELDS = [
  {
    key: "f2Timeout" as const,
    title: "Fase 2 — Subset Sum",
    desc: "Tiempo máximo por llamada DP en búsqueda N:N",
    unit: "seg",
    min: 1,
    max: 10,
  },
  {
    key: "f3Timeout" as const,
    title: "Fase 3 — Tolerancia",
    desc: "Tiempo máximo para grupos con diferencia ±5 cts",
    unit: "seg",
    min: 5,
    max: 30,
  },
  {
    key: "f4Timeout" as const,
    title: "Fase 4 — Profunda / F6-F7",
    desc: "Tiempo máximo para búsqueda global nocturna",
    unit: "seg",
    min: 15,
    max: 120,
  },
];

const DEPTH_FIELDS = [
  {
    key: "maxDepth" as const,
    title: "Profundidad máxima DP",
    desc: "Número máximo de candidatos en cada llamada al algoritmo DP (F2, F6, F7)",
    unit: "niveles",
    min: 2,
    max: 10,
  },
];

const TOGGLE_ITEMS = [
  {
    key: "strictMode",
    title: "Modo estricto de cuentas",
    desc: "No cruzar valores entre diferentes cuentas contables",
  },
  {
    key: "notifications",
    title: "Notificaciones automáticas",
    desc: "Alertar cuando termine cada fase del motor",
  },
  {
    key: "detailedLogs",
    title: "Guardar logs detallados",
    desc: "Mantener trazabilidad completa por 30 días",
  },
];

export default function ConfiguracionSection() {
  const { config, setConfig } = useReconciliation();
  const [local, setLocal] = useState({ ...config });
  const [toggles, setToggles] = useState({
    strictMode: true,
    notifications: false,
    detailedLogs: true,
  });
  const [saved, setSaved] = useState(false);
  const [notifStatus, setNotifStatus] = useState<"default" | "granted" | "denied">("default");

  // Leer estado actual del permiso al montar
  useEffect(() => {
    if ("Notification" in window) {
      setNotifStatus(Notification.permission as "default" | "granted" | "denied");
    }
  }, []);

  const handleSave = () => {
    setConfig(local);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleReset = () => {
    setLocal({ ...DEFAULT });
    setConfig({ ...DEFAULT });
  };

  const isDirty = JSON.stringify(local) !== JSON.stringify(config);

  return (
    <div className="bg-card rounded-2xl p-6 shadow-card space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-card-foreground">
            Ajustes del Motor
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Configuración del motor de conciliación v4 — F1 a F7b
          </p>
        </div>
        {saved && (
          <span className="flex items-center gap-1.5 text-xs text-success font-medium">
            <CheckCircle className="w-3.5 h-3.5" /> Guardado
          </span>
        )}
      </div>

      {/* Timeouts */}
      <div>
        <h4 className="text-sm font-semibold text-card-foreground mb-4 pb-2 border-b border-border">
          Timeouts por Fase
        </h4>
        <div className="space-y-2">
          {TIMEOUT_FIELDS.map(({ key, title, desc, unit, min, max }) => (
            <div
              key={key}
              className="flex justify-between items-center p-4 bg-muted/50 rounded-2xl"
            >
              <div>
                <h4 className="text-sm font-medium text-card-foreground">
                  {title}
                </h4>
                <p className="text-xs text-muted-foreground">{desc}</p>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  value={local[key]}
                  min={min}
                  max={max}
                  onChange={(e) =>
                    setLocal((p) => ({ ...p, [key]: Number(e.target.value) }))
                  }
                  className="w-20 px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary/30 text-card-foreground"
                />
                <span className="text-sm text-muted-foreground w-10">
                  {unit}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {min}–{max}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Profundidad */}
      <div>
        <h4 className="text-sm font-semibold text-card-foreground mb-4 pb-2 border-b border-border">
          Límites del Algoritmo DP
        </h4>
        <div className="space-y-2">
          {DEPTH_FIELDS.map(({ key, title, desc, unit, min, max }) => (
            <div
              key={key}
              className="flex justify-between items-center p-4 bg-muted/50 rounded-2xl"
            >
              <div>
                <h4 className="text-sm font-medium text-card-foreground">
                  {title}
                </h4>
                <p className="text-xs text-muted-foreground">{desc}</p>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  value={local[key]}
                  min={min}
                  max={max}
                  onChange={(e) =>
                    setLocal((p) => ({ ...p, [key]: Number(e.target.value) }))
                  }
                  className="w-20 px-3 py-2 border border-border rounded-lg text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary/30 text-card-foreground"
                />
                <span className="text-sm text-muted-foreground w-14">
                  {unit}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {min}–{max}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Toggles */}
      <div>
        <h4 className="text-sm font-semibold text-card-foreground mb-4 pb-2 border-b border-border">
          Opciones Generales
        </h4>
        <div className="space-y-2">
          {TOGGLE_ITEMS.map(({ key, title, desc }) => (
            <div
              key={key}
              className="flex justify-between items-center p-4 bg-muted/50 rounded-2xl"
            >
              <div>
                <h4 className="text-sm font-medium text-card-foreground">
                  {title}
                </h4>
                <p className="text-xs text-muted-foreground">{desc}</p>
              </div>
              <button
                onClick={() =>
                  setToggles((p) => ({
                    ...p,
                    [key]: !p[key as keyof typeof p],
                  }))
                }
                className={cn(
                  "w-11 h-6 rounded-full relative transition-colors",
                  toggles[key as keyof typeof toggles]
                    ? "bg-primary"
                    : "bg-border",
                )}
              >
                <div
                  className={cn(
                    "w-5 h-5 rounded-full bg-card absolute top-0.5 transition-all shadow-sm",
                    toggles[key as keyof typeof toggles]
                      ? "right-0.5"
                      : "right-[22px]",
                  )}
                />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Valores actuales */}
      <div className="bg-muted/30 rounded-2xl p-4 border border-border">
        <p className="text-xs font-medium text-muted-foreground mb-2">
          Configuración activa
        </p>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <span className="text-muted-foreground">
            F2 timeout:{" "}
            <strong className="text-card-foreground">
              {config.f2Timeout}s
            </strong>
          </span>
          <span className="text-muted-foreground">
            F3 timeout:{" "}
            <strong className="text-card-foreground">
              {config.f3Timeout}s
            </strong>
          </span>
          <span className="text-muted-foreground">
            F4 timeout:{" "}
            <strong className="text-card-foreground">
              {config.f4Timeout}s
            </strong>
          </span>
          <span className="text-muted-foreground">
            Profundidad:{" "}
            <strong className="text-card-foreground">
              {config.maxDepth} niveles
            </strong>
          </span>
        </div>
      </div>

      {/* Notificaciones */}
      <div>
        <h4 className="text-sm font-semibold text-card-foreground mb-4 pb-2 border-b border-border">
          Notificaciones
        </h4>
        <div className="flex items-center justify-between p-4 bg-muted/50 rounded-2xl">
          <div>
            <h4 className="text-sm font-medium text-card-foreground">
              Notificaciones de escritorio
            </h4>
            <p className="text-xs text-muted-foreground">
              Recibe alertas cuando termine una conciliación (estilo WhatsApp — solo cuando no estás mirando la pestaña)
            </p>
            {notifStatus === "denied" && (
              <p className="text-xs text-destructive mt-1">
                Permiso denegado. Ve a Configuración del navegador → Notificaciones para habilitarlas.
              </p>
            )}
          </div>
          <div className="flex items-center gap-3 shrink-0 ml-4">
            {notifStatus === "granted" ? (
              <span className="flex items-center gap-1.5 text-xs text-success font-medium">
                <Bell className="w-3.5 h-3.5" /> Activas
              </span>
            ) : notifStatus === "denied" ? (
              <span className="flex items-center gap-1.5 text-xs text-destructive font-medium">
                <BellOff className="w-3.5 h-3.5" /> Bloqueadas
              </span>
            ) : (
              <button
                onClick={async () => {
                  const granted = await requestNotificationPermission();
                  setNotifStatus(granted ? "granted" : "denied");
                }}
                className="px-4 py-2 rounded-full text-xs font-medium gradient-primary text-primary-foreground shadow hover:-translate-y-0.5 transition-all inline-flex items-center gap-1.5"
              >
                <Bell className="w-3.5 h-3.5" /> Activar
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="flex gap-4">
        <button
          onClick={handleSave}
          disabled={!isDirty}
          className={cn(
            "gradient-primary text-primary-foreground px-6 py-3 rounded-full text-sm font-medium shadow-lg transition-all inline-flex items-center gap-2",
            isDirty
              ? "hover:-translate-y-0.5"
              : "opacity-50 cursor-not-allowed",
          )}
        >
          <Save className="w-4 h-4" /> Guardar Cambios
        </button>
        <button
          onClick={handleReset}
          className="bg-card text-muted-foreground border border-border px-5 py-2.5 rounded-full text-sm hover:border-primary transition-colors inline-flex items-center gap-2"
        >
          <RotateCcw className="w-4 h-4" /> Restaurar Valores
        </button>
      </div>
    </div>
  );
}
