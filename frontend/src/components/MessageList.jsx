import React, { useEffect, useRef } from "react";
import { EyeOff, Trash2 } from "lucide-react";
import { api } from "../lib/api";

function formatTime(iso) {
    try {
        const d = new Date(iso);
        return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
        return "";
    }
}

function formatDate(iso) {
    try {
        const d = new Date(iso);
        return d.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" });
    } catch {
        return "";
    }
}

function AttachmentView({ att }) {
    const src = att.url?.startsWith("/") ? `${process.env.REACT_APP_BACKEND_URL}${att.url}` : att.url;
    return (
        <a href={src} target="_blank" rel="noopener noreferrer" className="block mt-2 w-fit">
            <img
                src={src}
                alt={att.type}
                className="attachment-img"
                loading="lazy"
                data-testid={`message-attachment-${att.type}`}
            />
        </a>
    );
}

export default function MessageList({ messages, currentUser, onMessageUpdated }) {
    const bottomRef = useRef(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
    }, [messages.length]);

    const isAdmin = currentUser?.role === "admin";

    const handleHide = async (m) => {
        try {
            const res = await api.post(`/messages/${m.id}/hide`);
            onMessageUpdated?.(res.data);
        } catch (e) {
            console.error(e);
        }
    };
    const handleUnhide = async (m) => {
        try {
            const res = await api.post(`/messages/${m.id}/unhide`);
            onMessageUpdated?.(res.data);
        } catch (e) {
            console.error(e);
        }
    };
    const handleDelete = async (m) => {
        if (!window.confirm("Delete this message permanently?")) return;
        try {
            await api.delete(`/messages/${m.id}`);
            onMessageUpdated?.({ ...m, _deleted: true });
        } catch (e) {
            console.error(e);
        }
    };

    // Group by day
    const groups = [];
    let lastDate = "";
    for (const m of messages) {
        const d = formatDate(m.created_at);
        if (d !== lastDate) {
            groups.push({ type: "divider", label: d, id: `div-${d}-${m.id}` });
            lastDate = d;
        }
        groups.push({ type: "msg", data: m });
    }

    return (
        <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4" data-testid="message-list">
            {messages.length === 0 && (
                <div
                    className="h-full flex flex-col items-center justify-center text-center gap-3"
                    data-testid="message-list-empty"
                >
                    <div className="ticker-label text-signal">// CHANNEL EMPTY</div>
                    <div className="font-heading font-extrabold text-3xl tracking-tight">
                        Start the conversation.
                    </div>
                    <div className="text-muted-foreground max-w-sm">
                        Send the first message, drop a picture, or search for a GIF.
                    </div>
                </div>
            )}
            {groups.map((g) =>
                g.type === "divider" ? (
                    <div key={g.id} className="flex items-center gap-3 my-4" data-testid="day-divider">
                        <div className="flex-1 h-px bg-border" />
                        <div className="ticker-label text-muted-foreground">{g.label}</div>
                        <div className="flex-1 h-px bg-border" />
                    </div>
                ) : (
                    <MessageRow
                        key={g.data.id}
                        m={g.data}
                        isAdmin={isAdmin}
                        currentUserId={currentUser?.id}
                        onHide={handleHide}
                        onUnhide={handleUnhide}
                        onDelete={handleDelete}
                    />
                )
            )}
            <div ref={bottomRef} />
        </div>
    );
}

function MessageRow({ m, isAdmin, currentUserId, onHide, onUnhide, onDelete }) {
    const hidden = m.hidden;
    const isOwn = m.user_id === currentUserId;
    const initials = (m.user_name || m.user_email || "?")
        .split(" ")
        .map((p) => p[0])
        .filter(Boolean)
        .slice(0, 2)
        .join("")
        .toUpperCase();

    return (
        <div
            className={`msg-row group flex gap-3 py-2 px-2 -mx-2 ${hidden ? "opacity-60" : ""}`}
            data-testid={`message-row-${m.id}`}
        >
            <div className="w-9 h-9 bg-ink text-white flex items-center justify-center font-heading font-bold text-sm shrink-0">
                {initials}
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                    <span className="font-heading font-bold text-sm" data-testid="message-author">
                        {m.user_name}
                    </span>
                    <span className="text-xs text-muted-foreground">{formatTime(m.created_at)}</span>
                    {hidden && (
                        <span className="ticker-label text-destructive" data-testid="message-hidden-label">
                            hidden by admin
                        </span>
                    )}
                </div>
                {m.content && (
                    <div
                        className="text-base leading-relaxed whitespace-pre-wrap break-words"
                        data-testid="message-content"
                    >
                        {m.content}
                    </div>
                )}
                {Array.isArray(m.attachments) &&
                    m.attachments.map((a, i) => <AttachmentView key={i} att={a} />)}
            </div>
            <div className="flex items-start gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {isAdmin && !hidden && (
                    <button
                        onClick={() => onHide(m)}
                        className="p-1.5 border border-border hover:border-ink"
                        title="Hide (moderate) message"
                        data-testid={`hide-message-${m.id}`}
                    >
                        <EyeOff className="w-3.5 h-3.5" />
                    </button>
                )}
                {isAdmin && hidden && (
                    <button
                        onClick={() => onUnhide(m)}
                        className="p-1.5 border border-border hover:border-ink text-xs"
                        title="Unhide message"
                        data-testid={`unhide-message-${m.id}`}
                    >
                        Unhide
                    </button>
                )}
                {(isAdmin || isOwn) && (
                    <button
                        onClick={() => onDelete(m)}
                        className="p-1.5 border border-border hover:border-destructive hover:text-destructive"
                        title="Delete message"
                        data-testid={`delete-message-${m.id}`}
                    >
                        <Trash2 className="w-3.5 h-3.5" />
                    </button>
                )}
            </div>
        </div>
    );
}
