import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

const PresenceContext = createContext({
    online: new Set(),
    isOnline: () => false,
    applyWsEvent: () => {},
});

export function PresenceProvider({ enabled, children }) {
    const [online, setOnline] = useState(() => new Set());
    const pollTimer = useRef(null);

    const refresh = useCallback(async () => {
        if (!enabled) return;
        try {
            const { data } = await api.get("/presence");
            setOnline(new Set(data?.online || []));
        } catch {
            /* ignore */
        }
    }, [enabled]);

    useEffect(() => {
        if (!enabled) return;
        refresh();
        // Gentle safety-net poll in case we missed a WS presence event (30s)
        pollTimer.current = setInterval(refresh, 30000);
        return () => {
            if (pollTimer.current) clearInterval(pollTimer.current);
        };
    }, [enabled, refresh]);

    const applyWsEvent = useCallback((evt) => {
        if (!evt || evt.type !== "presence:update" || !evt.user_id) return;
        setOnline((prev) => {
            const next = new Set(prev);
            if (evt.online) next.add(evt.user_id);
            else next.delete(evt.user_id);
            return next;
        });
    }, []);

    const isOnline = useCallback((userId) => (userId ? online.has(userId) : false), [online]);

    return (
        <PresenceContext.Provider value={{ online, isOnline, applyWsEvent, refresh }}>
            {children}
        </PresenceContext.Provider>
    );
}

export function usePresence() {
    return useContext(PresenceContext);
}
