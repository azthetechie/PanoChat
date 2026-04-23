import React, { useCallback, useEffect, useRef } from "react";

const STORAGE_KEY = "panorama_notifications_enabled";
const MUTE_UNTIL_KEY = "panorama_mute_until";
const QUIET_HOURS_KEY = "panorama_quiet_hours";

function _readJSON(key) {
    try {
        const v = localStorage.getItem(key);
        return v ? JSON.parse(v) : null;
    } catch {
        return null;
    }
}

function _writeJSON(key, value) {
    try {
        if (value == null) localStorage.removeItem(key);
        else localStorage.setItem(key, JSON.stringify(value));
    } catch {
        /* ignore */
    }
}

// --- Mute until (one-off snooze) ---
export function getMuteUntil() {
    const v = _readJSON(MUTE_UNTIL_KEY);
    if (!v) return null;
    const ts = new Date(v);
    if (isNaN(ts.getTime()) || ts.getTime() < Date.now()) {
        _writeJSON(MUTE_UNTIL_KEY, null);
        return null;
    }
    return ts;
}

export function setMuteUntil(ts) {
    if (!ts) return _writeJSON(MUTE_UNTIL_KEY, null);
    _writeJSON(MUTE_UNTIL_KEY, new Date(ts).toISOString());
}

export function snoozeFor(durationMs) {
    setMuteUntil(Date.now() + durationMs);
}

export function snoozeUntilTomorrowMorning() {
    const next = new Date();
    next.setDate(next.getDate() + 1);
    next.setHours(9, 0, 0, 0);
    setMuteUntil(next);
}

// --- Daily quiet hours (recurring) ---
const DEFAULT_QUIET = { enabled: false, start: "22:00", end: "07:00" };

export function getQuietHours() {
    const raw = _readJSON(QUIET_HOURS_KEY);
    return { ...DEFAULT_QUIET, ...(raw || {}) };
}

export function setQuietHours(qh) {
    _writeJSON(QUIET_HOURS_KEY, { ...DEFAULT_QUIET, ...qh });
}

function _parseHHMM(s) {
    const [h, m] = (s || "00:00").split(":").map((n) => parseInt(n, 10) || 0);
    return h * 60 + m;
}

export function isInQuietHours(now = new Date()) {
    const qh = getQuietHours();
    if (!qh.enabled) return false;
    const cur = now.getHours() * 60 + now.getMinutes();
    const start = _parseHHMM(qh.start);
    const end = _parseHHMM(qh.end);
    if (start === end) return false;
    if (start < end) return cur >= start && cur < end; // same-day window
    return cur >= start || cur < end; // overnight (e.g. 22:00→07:00)
}

// --- Enabled / permission ---
export function notificationsEnabled() {
    if (typeof window === "undefined") return false;
    if (!("Notification" in window)) return false;
    if (Notification.permission !== "granted") return false;
    if (localStorage.getItem(STORAGE_KEY) !== "1") return false;
    if (getMuteUntil()) return false;
    if (isInQuietHours()) return false;
    return true;
}

export function setNotificationPreference(enabled) {
    if (typeof window === "undefined") return;
    localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
}

export function getNotificationPreference() {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(STORAGE_KEY) === "1";
}

export async function requestNotificationPermission() {
    if (!("Notification" in window)) return "denied";
    if (Notification.permission === "granted") return "granted";
    return Notification.requestPermission();
}

export function showDesktopNotification(title, body, onClick) {
    if (!notificationsEnabled()) return;
    try {
        const n = new Notification(title, { body, silent: false });
        if (onClick)
            n.onclick = () => {
                window.focus();
                onClick();
                n.close();
            };
    } catch {
        /* ignore */
    }
}

export function useDesktopNotifications({ user, channelsById, activeChannelId }) {
    const userRef = useRef(user);
    const channelsRef = useRef(channelsById);
    const activeRef = useRef(activeChannelId);

    useEffect(() => {
        userRef.current = user;
    }, [user]);
    useEffect(() => {
        channelsRef.current = channelsById;
    }, [channelsById]);
    useEffect(() => {
        activeRef.current = activeChannelId;
    }, [activeChannelId]);

    const notify = useCallback((evt) => {
        if (!notificationsEnabled()) return;
        if (!evt || evt.type !== "message:new" || !evt.message) return;
        const m = evt.message;
        const me = userRef.current;
        if (!me || m.user_id === me.id) return;
        const isActive = activeRef.current === m.channel_id;
        if (document.visibilityState === "visible" && isActive) return;
        const channel = channelsRef.current?.[m.channel_id];
        const isDm = channel?.type === "dm";
        const mentioned = Array.isArray(m.mentions) && m.mentions.includes(me.id);
        if (!isDm && !mentioned) return;
        const title = isDm ? `${m.user_name}` : `@${m.user_name} in #${channel?.name || "chat"}`;
        const body = (m.content || "[attachment]").slice(0, 140);
        showDesktopNotification(title, body);
    }, []);

    return { notify };
}
