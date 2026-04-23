import React, { useCallback, useEffect, useRef } from "react";

const STORAGE_KEY = "panorama_notifications_enabled";

export function notificationsEnabled() {
    if (typeof window === "undefined") return false;
    if (!("Notification" in window)) return false;
    if (Notification.permission !== "granted") return false;
    return localStorage.getItem(STORAGE_KEY) === "1";
}

export function setNotificationPreference(enabled) {
    if (typeof window === "undefined") return;
    localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
}

export async function requestNotificationPermission() {
    if (!("Notification" in window)) return "denied";
    if (Notification.permission === "granted") return "granted";
    const res = await Notification.requestPermission();
    return res;
}

export function showDesktopNotification(title, body, onClick) {
    if (!notificationsEnabled()) return;
    try {
        const n = new Notification(title, { body, silent: false });
        if (onClick) n.onclick = () => {
            window.focus();
            onClick();
            n.close();
        };
    } catch {
        /* ignore */
    }
}

/**
 * Hook — given the current user and an event stream, surface desktop
 * notifications for DM messages or @mentions while the window is unfocused.
 */
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
        // Only notify when window is hidden OR message is not in active channel
        const isActive = activeRef.current === m.channel_id;
        if (document.visibilityState === "visible" && isActive) return;

        const channel = channelsRef.current?.[m.channel_id];
        const isDm = channel?.type === "dm";
        const mentioned = Array.isArray(m.mentions) && m.mentions.includes(me.id);

        if (!isDm && !mentioned) return; // only DMs + mentions ping

        const title = isDm ? `${m.user_name}` : `@${m.user_name} in #${channel?.name || "chat"}`;
        const body = (m.content || "[attachment]").slice(0, 140);
        showDesktopNotification(title, body);
    }, []);

    return { notify };
}
