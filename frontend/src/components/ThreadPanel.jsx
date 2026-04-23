import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { X, MessageSquare } from "lucide-react";
import { api, getErrorMessage } from "../lib/api";
import MessageComposer from "./MessageComposer";

function formatTime(iso) {
    try {
        return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
        return "";
    }
}

function AttachmentView({ att }) {
    const src = att.url?.startsWith("/")
        ? `${process.env.REACT_APP_BACKEND_URL}${att.url}`
        : att.url;
    return (
        <a href={src} target="_blank" rel="noopener noreferrer" className="block mt-2 w-fit">
            <img src={src} alt={att.type} className="attachment-img" loading="lazy" />
        </a>
    );
}

/**
 * Right-side thread panel. Controlled by ChatPage.
 * - parentMessage: the message object to thread from
 * - replies: list of replies (also updated live via WS events from ChatPage)
 * - onClose: close handler
 * - onReplyPosted: called after composer posts a reply so ChatPage can sync state
 */
export default function ThreadPanel({
    parent,
    replies = [],
    currentUser,
    allUsers = [],
    onClose,
    onReplyPosted,
    onReplyLoaded,
}) {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const bottomRef = useRef(null);

    const load = useCallback(async () => {
        if (!parent?.id) return;
        setLoading(true);
        setError("");
        try {
            const { data } = await api.get(`/messages/${parent.id}/thread`);
            // data[0] is the parent itself; the rest are replies
            const loadedReplies = data.slice(1);
            onReplyLoaded?.(loadedReplies);
        } catch (e) {
            setError(getErrorMessage(e));
        } finally {
            setLoading(false);
        }
    }, [parent?.id, onReplyLoaded]);

    useEffect(() => {
        load();
    }, [load]);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
    }, [replies.length]);

    const usersById = useMemo(() => {
        const m = {};
        allUsers.forEach((u) => (m[u.id] = u));
        return m;
    }, [allUsers]);

    if (!parent) return null;

    return (
        <aside
            className="flex flex-col h-full w-full lg:w-[420px] border-l border-border bg-white"
            data-testid="thread-panel"
        >
            <header className="flex items-center justify-between px-4 md:px-5 py-3 border-b border-border">
                <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare className="w-4 h-4 shrink-0" />
                    <div className="min-w-0">
                        <div className="ticker-label text-signal">// THREAD</div>
                        <div className="font-heading font-extrabold text-sm truncate">
                            Reply to {parent.user_name}
                        </div>
                    </div>
                </div>
                <button
                    className="p-2 border border-border hover:border-ink"
                    onClick={onClose}
                    data-testid="thread-close-button"
                >
                    <X className="w-4 h-4" />
                </button>
            </header>

            <div className="flex-1 overflow-y-auto p-4 space-y-4" data-testid="thread-messages">
                {/* Parent */}
                <ThreadBubble m={parent} usersById={usersById} currentUserId={currentUser?.id} kind="parent" />
                <div className="flex items-center gap-3">
                    <div className="flex-1 h-px bg-border" />
                    <div className="ticker-label text-muted-foreground" data-testid="thread-reply-count-label">
                        {replies.length === 0 ? "No replies yet" : `${replies.length} ${replies.length === 1 ? "reply" : "replies"}`}
                    </div>
                    <div className="flex-1 h-px bg-border" />
                </div>

                {loading && <div className="text-xs text-muted-foreground">Loading thread…</div>}
                {error && <div className="text-xs text-destructive">{error}</div>}

                {replies.map((r) => (
                    <ThreadBubble
                        key={r.id}
                        m={r}
                        usersById={usersById}
                        currentUserId={currentUser?.id}
                    />
                ))}
                <div ref={bottomRef} />
            </div>

            <MessageComposer
                channelId={parent.channel_id}
                parentId={parent.id}
                disabled={false}
                onSent={(m) => onReplyPosted?.(m)}
                allUsers={allUsers}
                compact
            />
        </aside>
    );
}

function ThreadBubble({ m, usersById, currentUserId, kind }) {
    const initials = (m.user_name || m.user_email || "?")
        .split(" ")
        .map((p) => p[0])
        .filter(Boolean)
        .slice(0, 2)
        .join("")
        .toUpperCase();
    const mentionsMe =
        Array.isArray(m.mentions) && currentUserId && m.mentions.includes(currentUserId);

    return (
        <div
            className={`flex gap-3 ${
                kind === "parent" ? "border-b border-border pb-4" : ""
            } ${mentionsMe ? "bg-signal/5 border-l-4 border-l-signal pl-2" : ""}`}
            data-testid={`thread-bubble-${m.id}`}
        >
            <div className="w-8 h-8 bg-ink text-white flex items-center justify-center font-heading font-bold text-xs shrink-0">
                {initials}
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                    <span className="font-heading font-bold text-sm">{m.user_name}</span>
                    <span className="text-xs text-muted-foreground">{formatTime(m.created_at)}</span>
                </div>
                {m.content && (
                    <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                        {m.content}
                    </div>
                )}
                {Array.isArray(m.attachments) &&
                    m.attachments.map((a, i) => <AttachmentView key={i} att={a} />)}
            </div>
        </div>
    );
}
