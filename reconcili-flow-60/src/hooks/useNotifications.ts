import { useEffect, useRef } from "react";

// ── Service Worker ────────────────────────────────────────────────────────────
let swRegistered = false;
let swRegistration: ServiceWorkerRegistration | null = null;

async function registerSW(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator)) return null;
  if (swRegistered && swRegistration) return swRegistration;
  try {
    const reg = await navigator.serviceWorker.register("/sw.js");
    swRegistered = true;
    swRegistration = reg;
    console.log("[Notif] SW registrado:", reg.scope);
    return reg;
  } catch (e) {
    console.warn("[Notif] SW no registrado:", e);
    return null;
  }
}

// ── Permiso ───────────────────────────────────────────────────────────────────
export async function requestNotificationPermission(): Promise<boolean> {
  if (!("Notification" in window)) {
    console.warn("[Notif] API de Notification no disponible");
    return false;
  }
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") {
    console.warn("[Notif] Permiso denegado por el usuario");
    return false;
  }
  console.log("[Notif] Solicitando permiso...");
  const result = await Notification.requestPermission();
  console.log("[Notif] Permiso:", result);
  return result === "granted";
}

// ── Enviar notificación ───────────────────────────────────────────────────────
/**
 * Envía una notificación estilo WhatsApp:
 * - Solo cuando el usuario NO está mirando la pestaña (document.hidden)
 * - Via Service Worker para funcionar con el navegador minimizado
 * - tag: agrupa/reemplaza notificaciones del mismo tipo
 * - requireInteraction: no desaparece sola
 */
export async function sendNotification(
  title: string,
  body: string,
  tag: string = "conciliador",
): Promise<void> {
  if (!("Notification" in window)) return;
  if (Notification.permission !== "granted") {
    console.warn("[Notif] Sin permiso — no se envía notificación");
    return;
  }

  // Solo notificar si el usuario no está mirando la pestaña
  if (!document.hidden) {
    console.log("[Notif] Pestaña visible — notificación omitida");
    return;
  }

  const reg = await registerSW();

  if (reg) {
    // Esperar a que el SW esté activo
    const active = reg.active ?? (await navigator.serviceWorker.ready).active;
    if (active) {
      active.postMessage({ type: "NOTIFY", title, body, tag });
      console.log("[Notif] Enviada via SW:", title);
      return;
    }
  }

  // Fallback: Notification API directa (sin SW)
  try {
    new Notification(title, {
      body,
      tag,
      icon: "/favicon.ico",
      requireInteraction: true,
    });
    console.log("[Notif] Enviada via API directa:", title);
  } catch (e) {
    console.warn("[Notif] Error al enviar:", e);
  }
}

// ── Hook principal ────────────────────────────────────────────────────────────
/**
 * Registra el SW y solicita permiso de notificaciones al montar.
 * Usar una sola vez en el componente raíz (AppLayout en Index.tsx).
 */
export function useNotifications() {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    // Registrar SW inmediatamente
    registerSW();

    // Solicitar permiso con delay para no interrumpir la carga
    if ("Notification" in window && Notification.permission === "default") {
      setTimeout(async () => {
        const granted = await requestNotificationPermission();
        if (granted) {
          console.log("[Notif] Permiso concedido — notificaciones activas");
        }
      }, 2000);
    } else if ("Notification" in window) {
      console.log("[Notif] Estado actual:", Notification.permission);
    }
  }, []);
}
