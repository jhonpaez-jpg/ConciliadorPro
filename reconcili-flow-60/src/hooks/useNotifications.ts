import { useEffect, useRef } from "react";

// Registra el Service Worker una sola vez
let swRegistered = false;
async function registerSW() {
  if (swRegistered || !("serviceWorker" in navigator)) return;
  try {
    await navigator.serviceWorker.register("/sw.js");
    swRegistered = true;
  } catch (e) {
    console.warn("SW no registrado:", e);
  }
}

// Solicita permiso de notificaciones
export async function requestNotificationPermission(): Promise<boolean> {
  if (!("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  const result = await Notification.requestPermission();
  return result === "granted";
}

/**
 * Envía una notificación solo si el usuario NO está mirando la pestaña.
 * Usa el Service Worker para que funcione incluso con el navegador minimizado.
 * - tag: agrupa notificaciones del mismo tipo (reemplaza en vez de apilar)
 * - requireInteraction: no desaparece sola
 */
export async function sendNotification(
  title: string,
  body: string,
  tag: string = "conciliador",
) {
  if (!("Notification" in window)) return;
  if (Notification.permission !== "granted") return;

  // Solo notificar si el usuario no está mirando la pestaña
  if (!document.hidden) return;

  await registerSW();

  // Intentar via Service Worker (funciona en background)
  if ("serviceWorker" in navigator) {
    const reg = await navigator.serviceWorker.ready.catch(() => null);
    if (reg) {
      reg.active?.postMessage({ type: "NOTIFY", title, body, tag });
      return;
    }
  }

  // Fallback: Notification API directa
  new Notification(title, {
    body,
    tag,
    icon: "/favicon.ico",
    requireInteraction: true,
  });
}

// Hook que inicializa el SW y solicita permiso al montar
export function useNotifications() {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    registerSW();
    // Solicitar permiso automáticamente (solo si no se ha decidido)
    if ("Notification" in window && Notification.permission === "default") {
      // Pequeño delay para no interrumpir la carga inicial
      setTimeout(() => requestNotificationPermission(), 3000);
    }
  }, []);
}
