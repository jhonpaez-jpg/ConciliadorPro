/**
 * AppNotification — Toast in-app estilo WhatsApp/Slack
 * Aparece cuando el usuario SÍ está mirando la pestaña.
 * Para cuando no la mira, el SW envía la notificación del OS.
 */
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, CalendarClock, XCircle, X } from "lucide-react";

export type NotifType = "success" | "scheduled" | "error" | "info";

export interface AppNotifData {
  id: string;
  type: NotifType;
  title: string;
  body: string;
}

// ── Singleton bus de eventos ──────────────────────────────────────────────────
type Listener = (n: AppNotifData) => void;
const listeners: Listener[] = [];

export function emitAppNotification(n: Omit<AppNotifData, "id">) {
  const notif: AppNotifData = { ...n, id: `${Date.now()}-${Math.random()}` };
  listeners.forEach((l) => l(notif));
}

// ── Estilos por tipo ──────────────────────────────────────────────────────────
const STYLES: Record<
  NotifType,
  { icon: React.ReactNode; bar: string; bg: string; title: string }
> = {
  success: {
    icon: <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />,
    bar: "bg-emerald-400",
    bg: "from-[#0f2a1e] to-[#1a3a2a]",
    title: "text-emerald-300",
  },
  scheduled: {
    icon: <CalendarClock className="w-5 h-5 text-violet-400 shrink-0" />,
    bar: "bg-violet-400",
    bg: "from-[#1a1535] to-[#231d45]",
    title: "text-violet-300",
  },
  error: {
    icon: <XCircle className="w-5 h-5 text-red-400 shrink-0" />,
    bar: "bg-red-400",
    bg: "from-[#2a0f0f] to-[#3a1a1a]",
    title: "text-red-300",
  },
  info: {
    icon: <CalendarClock className="w-5 h-5 text-sky-400 shrink-0" />,
    bar: "bg-sky-400",
    bg: "from-[#0f1e2a] to-[#1a2d3a]",
    title: "text-sky-300",
  },
};

// ── Item individual ───────────────────────────────────────────────────────────
function NotifItem({
  notif,
  onClose,
}: {
  notif: AppNotifData;
  onClose: () => void;
}) {
  const s = STYLES[notif.type];
  const [visible, setVisible] = useState(false);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    // Entrada
    requestAnimationFrame(() => setVisible(true));
    // Auto-cerrar a los 6s
    const t = setTimeout(() => handleClose(), 6000);
    return () => clearTimeout(t);
  }, []);

  const handleClose = () => {
    setLeaving(true);
    setTimeout(onClose, 350);
  };

  return (
    <div
      className={`
        relative overflow-hidden rounded-2xl shadow-2xl border border-white/10
        bg-gradient-to-br ${s.bg}
        backdrop-blur-xl
        transition-all duration-350 ease-out
        ${visible && !leaving ? "opacity-100 translate-y-0 scale-100" : "opacity-0 translate-y-4 scale-95"}
        w-[340px] max-w-[calc(100vw-2rem)]
      `}
      style={{ transition: "opacity 350ms, transform 350ms" }}
    >
      {/* Barra de progreso superior */}
      <div className={`absolute top-0 left-0 h-[3px] w-full ${s.bar} opacity-80`}>
        <div
          className="h-full bg-white/30 origin-left"
          style={{ animation: "shrink-bar 6s linear forwards" }}
        />
      </div>

      <div className="flex items-start gap-3 p-4 pt-5">
        {/* Icono */}
        <div className="mt-0.5">{s.icon}</div>

        {/* Contenido */}
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-semibold leading-tight ${s.title}`}>
            {notif.title}
          </p>
          <p className="text-xs text-white/60 mt-1 leading-relaxed">
            {notif.body}
          </p>
        </div>

        {/* Cerrar */}
        <button
          onClick={handleClose}
          className="text-white/30 hover:text-white/70 transition-colors mt-0.5 shrink-0"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Brillo sutil en la esquina */}
      <div className="absolute -top-8 -right-8 w-24 h-24 rounded-full bg-white/5 blur-2xl pointer-events-none" />
    </div>
  );
}

// ── Contenedor global ─────────────────────────────────────────────────────────
export default function AppNotificationContainer() {
  const [notifs, setNotifs] = useState<AppNotifData[]>([]);
  const listenerRef = useRef<Listener | null>(null);

  useEffect(() => {
    const listener: Listener = (n) => {
      setNotifs((prev) => [...prev.slice(-3), n]); // máx 4 a la vez
    };
    listenerRef.current = listener;
    listeners.push(listener);
    return () => {
      const idx = listeners.indexOf(listener);
      if (idx >= 0) listeners.splice(idx, 1);
    };
  }, []);

  if (notifs.length === 0) return null;

  return (
    <>
      {/* Keyframe para la barra de progreso */}
      <style>{`
        @keyframes shrink-bar {
          from { transform: scaleX(1); }
          to   { transform: scaleX(0); }
        }
      `}</style>

      <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-3 items-end pointer-events-none">
        {notifs.map((n) => (
          <div key={n.id} className="pointer-events-auto">
            <NotifItem
              notif={n}
              onClose={() =>
                setNotifs((prev) => prev.filter((x) => x.id !== n.id))
              }
            />
          </div>
        ))}
      </div>
    </>
  );
}
