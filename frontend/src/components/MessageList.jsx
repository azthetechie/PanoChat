import React, { useEffect, useRef, useState } from "react";
import { EyeOff, Trash2, Smile } from "lucide-react";
import { api } from "../lib/api";

const QUICK_REACTIONS = ["👍", "❤️", "😂", "🎉", "🚀", "👀", "🙏", "🔥"];

function formatTime(iso) {
    try {
        return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
        return "";
    }
}
function formatDate(iso) {
    try {
        return new Date(iso).toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" });
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

/** Parse mentions: wrap `@Name` runs that match passed mention IDs into span. */
function renderContentWithMentions(content, mentionIds = [], usersById = {}) {
    if (!content) return null;
    const mentionNames = mentionIds
        .map((id) => (usersById[id]?.name || "").trim())
        .filter(Boolean);
    if (mentionNames.length === 0) return content;

    // Build a regex that matches @<name> for any mentioned name
    const pattern = new RegExp(
        `@(${mentionNames.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`,
        "g"
    );
    const parts = [];
    let last = 0;
    let m;
    while ((m = pattern.exec(content)) !== null) {
        if (m.index > last) parts.push(content.slice(last, m.index));
        parts.push(
            <span
                key={`mention-${m.index}`}
                className="bg-signal/10 text-signal font-bold px-1"
                data-testid="mention-highlight"
            >
                @{m[1]}
            </span>
        );
        last = m.index + m[0].length;
    }
    if (last < content.length) parts.push(content.slice(last));
    return parts;
}

export default function MessageList({ messages, currentUser, onMessageUpdated, usersById = {} }) {
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
    const handleReact = async (m, emoji) => {
        try {
            const res = await api.post(`/messages/${m.id}/react`, { emoji });
            onMessageUpdated?.(res.data);
        } catch (e) {
            console.error(e);
        }
    };

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
                        onReact={handleReact}
                        usersById={usersById}
                    />
                )
            )}
            <div ref={bottomRef} />
        </div>
    );
}

function MessageRow({ m, isAdmin, currentUserId, onHide, onUnhide, onDelete, onReact, usersById }) {
    const hidden = m.hidden;
    const isOwn = m.user_id === currentUserId;
    const [pickerOpen, setPickerOpen] = useState(false);
    const initials = (m.user_name || m.user_email || "?")
        .split(" ")
        .map((p) => p[0])
        .filter(Boolean)
        .slice(0, 2)
        .join("")
        .toUpperCase();
    const mentionsMe =
        Array.isArray(m.mentions) && currentUserId && m.mentions.includes(currentUserId);
    const reactions = m.reactions || {};
    const reactionEntries = Object.entries(reactions).filter(([, arr]) => arr && arr.length);

    return (
        <div
            className={`msg-row group flex gap-3 py-2 px-2 -mx-2 ${hidden ? "opacity-60" : ""} ${
                mentionsMe ? "border-l-4 border-l-signal bg-signal/5 pl-3" : ""
            }`}
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
                    {mentionsMe && (
                        <span className="ticker-label text-signal" data-testid="mentions-me-badge">
                            mentions you
                        </span>
                    )}
                </div>
                {m.content && (
                    <div
                        className="text-base leading-relaxed whitespace-pre-wrap break-words"
                        data-testid="message-content"
                    >
                        {renderContentWithMentions(m.content, m.mentions, usersById)}
                    </div>
                )}
                {Array.isArray(m.attachments) &&
                    m.attachments.map((a, i) => <AttachmentView key={i} att={a} />)}
                {reactionEntries.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2" data-testid="message-reactions">
                        {reactionEntries.map(([emoji, userIds]) => {
                            const mine = userIds.includes(currentUserId);
                            return (
                                <button
                                    key={emoji}
                                    onClick={() => onReact(m, emoji)}
                                    className={`flex items-center gap-1 px-2 py-0.5 border text-xs transition-colors ${
                                        mine
                                            ? "border-signal bg-signal/10 text-ink"
                                            : "border-border hover:border-ink"
                                    }`}
                                    data-testid={`reaction-${emoji}-${m.id}`}
                                >
                                    <span>{emoji}</span>
                                    <span className="font-bold">{userIds.length}</span>
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>
            <div className="flex items-start gap-1 opacity-0 group-hover:opacity-100 transition-opacity relative">
                <button
                    onClick={() => setPickerOpen((v) => !v)}
                    className="p-1.5 border border-border hover:border-ink"
                    title="Add reaction"
                    data-testid={`open-reaction-picker-${m.id}`}
                >
                    <Smile className="w-3.5 h-3.5" />
                </button>
                {pickerOpen && (
                    <div
                        className="absolute right-0 top-8 z-20 bg-white border border-ink p-1 flex gap-1 shadow-lg"
                        data-testid={`reaction-picker-${m.id}`}
                    >
                        {QUICK_REACTIONS.map((e) => (
                            <button
                                key={e}
                                onClick={() => {
                                    onReact(m, e);
                                    setPickerOpen(false);
                                }}
                                className="text-lg leading-none px-1.5 py-1 hover:bg-surface"
                                data-testid={`pick-reaction-${e}-${m.id}`}
                            >
                                {e}
                            </button>
                        ))}
                    </div>
                )}
                {isAdmin && !hidden && (
                    <button
                        onClick={() => onHide(m)}
                        className="p-1.5 border border-border hover:border-ink"
                        title="Hide message"
                        data-testid={`hide-message-${m.id}`}
                    >
                        <EyeOff className="w-3.5 h-3.5" />
                    </button>
                )}
                {isAdmin && hidden && (
                    <button
                        onClick={() => onUnhide(m)}
                        className="p-1.5 border border-border hover:border-ink text-xs"
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
