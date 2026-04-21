import { useEffect, useRef } from "react";
import { emitAppNotification, type NotifType } from "@/components/AppNotification";

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
  if (!("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  const result = await Notification.requestPermission();
  console.log("[Notif] Permiso:", result);
  return result === "granted";
}

// ── Enviar notificación ───────────────────────────────────────────────────────
/**
 * Comportamiento dual:
 * - Pestaña VISIBLE  → toast in-app animado (AppNotification)
 * - Pestaña OCULTA   → notificación del OS via Service Worker
 */
export async function sendNotification(
  title: string,
  body: string,
  tag: string = "conciliador",
  type: NotifType = "info",
): Promise<void> {
  if (!("Notification" in window)) return;

  if (document.hidden) {
    // ── OS notification (pestaña oculta / navegador minimizado) ──────────────
    if (Notification.permission !== "granted") return;

    const reg = await registerSW();
    if (reg) {
      const active = reg.active ?? (await navigator.serviceWorker.ready).active;
      if (active) {
        active.postMessage({ type: "NOTIFY", title, body, tag, notifType: type });
        console.log("[Notif] OS via SW:", title);
        return;
      }
    }
    // Fallback directo
    try {
      new Notification(title, { body, tag, icon: "/favicon.ico", requireInteraction: true });
    } catch {}
  } else {
    // ── In-app toast (pestaña visible) ────────────────────────────────────────
    emitAppNotification({ type, title, body });
    console.log("[Notif] In-app:", title);
  }
}

// ── Hook principal ────────────────────────────────────────────────────────────
export function useNotifications() {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    registerSW();

    if ("Notification" in window && Notification.permission === "default") {
      setTimeout(async () => {
        const granted = await requestNotificationPermission();
        if (granted) console.log("[Notif] Permiso concedido");
      }, 2000);
    }
  }, []);
}
