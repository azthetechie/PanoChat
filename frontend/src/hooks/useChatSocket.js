import { useCallback, useEffect, useRef, useState } from "react";
import { wsUrl } from "../lib/api";

/**
 * WebSocket hook that reconnects, authenticates via token, and exposes
 * subscribe/unsubscribe + a message handler.
 *
 * onMessage receives parsed JSON messages.
 */
export function useChatSocket({ token, onMessage, enabled = true }) {
    const wsRef = useRef(null);
    const reconnectTimer = useRef(null);
    const subscribedRef = useRef(new Set());
    const onMessageRef = useRef(onMessage);
    const [status, setStatus] = useState("idle"); // idle | connecting | open | closed

    useEffect(() => {
        onMessageRef.current = onMessage;
    }, [onMessage]);

    const connect = useCallback(() => {
        if (!enabled || !token) return;
        setStatus("connecting");
        const ws = new WebSocket(wsUrl(token));
        wsRef.current = ws;
        ws.onopen = () => {
            setStatus("open");
            // Re-subscribe to prior channels
            subscribedRef.current.forEach((cid) => {
                ws.send(JSON.stringify({ type: "subscribe", channel_id: cid }));
            });
        };
        ws.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                onMessageRef.current?.(data);
            } catch {
                /* ignore */
            }
        };
        ws.onclose = () => {
            setStatus("closed");
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            reconnectTimer.current = setTimeout(connect, 2000);
        };
        ws.onerror = () => {
            try {
                ws.close();
            } catch {
                /* ignore */
            }
        };
    }, [token, enabled]);

    useEffect(() => {
        connect();
        return () => {
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            try {
                wsRef.current?.close();
            } catch {
                /* ignore */
            }
        };
    }, [connect]);

    const subscribe = useCallback((channelId) => {
        if (!channelId) return;
        subscribedRef.current.add(channelId);
        const ws = wsRef.current;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "subscribe", channel_id: channelId }));
        }
    }, []);

    const unsubscribe = useCallback((channelId) => {
        if (!channelId) return;
        subscribedRef.current.delete(channelId);
        const ws = wsRef.current;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "unsubscribe", channel_id: channelId }));
        }
    }, []);

    return { status, subscribe, unsubscribe };
}
