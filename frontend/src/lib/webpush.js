/**
 * Web-Push helpers: registers the service worker, subscribes/unsubscribes,
 * and reports status for the Profile UI.
 */
import { api } from "./api";

const SW_PATH = "/sw.js";
const PREF_KEY = "panorama_push_enabled";

export function isPushSupported() {
    return (
        typeof window !== "undefined" &&
        "serviceWorker" in navigator &&
        "PushManager" in window &&
        "Notification" in window
    );
}

export function getPushPreference() {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(PREF_KEY) === "1";
}

function setPushPreference(val) {
    if (typeof window === "undefined") return;
    localStorage.setItem(PREF_KEY, val ? "1" : "0");
}

function urlB64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const b64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = window.atob(b64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
}

async function getRegistration() {
    if (!isPushSupported()) return null;
    let reg = await navigator.serviceWorker.getRegistration(SW_PATH);
    if (!reg) {
        reg = await navigator.serviceWorker.register(SW_PATH);
    }
    await navigator.serviceWorker.ready;
    return reg;
}

export async function getSubscriptionStatus() {
    if (!isPushSupported()) return { supported: false, subscribed: false };
    const reg = await navigator.serviceWorker.getRegistration(SW_PATH);
    if (!reg) return { supported: true, subscribed: false };
    const sub = await reg.pushManager.getSubscription();
    return { supported: true, subscribed: !!sub };
}

export async function enablePush() {
    if (!isPushSupported()) throw new Error("Web-push is not supported in this browser.");

    // Permission gate
    if (Notification.permission !== "granted") {
        const res = await Notification.requestPermission();
        if (res !== "granted") throw new Error("Notification permission denied.");
    }

    const reg = await getRegistration();
    if (!reg) throw new Error("Could not register service worker.");

    // Fetch VAPID public key
    const { data } = await api.get("/push/vapid-public-key");
    const appServerKey = urlB64ToUint8Array(data.public_key);

    // Re-use existing or subscribe fresh
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
        sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: appServerKey,
        });
    }

    const json = sub.toJSON();
    await api.post("/push/subscribe", {
        endpoint: json.endpoint,
        keys: { p256dh: json.keys?.p256dh, auth: json.keys?.auth },
    });

    setPushPreference(true);
    return sub;
}

export async function disablePush() {
    setPushPreference(false);
    const reg = await navigator.serviceWorker.getRegistration(SW_PATH);
    if (!reg) return;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return;
    try {
        await api.post("/push/unsubscribe", { endpoint: sub.endpoint });
    } catch (_) {
        /* ignore */
    }
    try {
        await sub.unsubscribe();
    } catch (_) {
        /* ignore */
    }
}

export async function sendTestPush() {
    await api.post("/push/test");
}
