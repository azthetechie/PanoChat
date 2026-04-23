import React from "react";
import { usePresence } from "../context/PresenceContext";

/**
 * Tiny presence indicator shown in a corner of an avatar.
 * size: "sm" (default, 10px) | "xs" (8px) | "md" (12px)
 */
export default function PresenceDot({ userId, size = "sm", className = "" }) {
    const { isOnline } = usePresence();
    const online = isOnline(userId);
    const dim =
        size === "xs" ? "w-2 h-2" : size === "md" ? "w-3 h-3" : "w-2.5 h-2.5";
    return (
        <span
            aria-label={online ? "online" : "offline"}
            className={`inline-block border-2 border-white ${dim} ${
                online ? "bg-green-600" : "bg-muted-foreground"
            } ${className}`}
            data-testid={`presence-dot-${userId}-${online ? "online" : "offline"}`}
        />
    );
}
