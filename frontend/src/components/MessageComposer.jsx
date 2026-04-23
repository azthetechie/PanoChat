import React, { useMemo, useRef, useState } from "react";
import { ImagePlus, Smile, SendHorizontal, X, Paperclip, AtSign } from "lucide-react";
import { api, getErrorMessage } from "../lib/api";
import GifPicker from "./GifPicker";
import PresenceDot from "./PresenceDot";

export default function MessageComposer({
    channelId,
    disabled,
    onSent,
    allUsers = [],
    parentId = null,
    compact = false,
}) {
    const [content, setContent] = useState("");
    const [attachments, setAttachments] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [gifOpen, setGifOpen] = useState(false);
    const [error, setError] = useState("");
    // mention autocomplete
    const [mentionQuery, setMentionQuery] = useState(null); // null or { q, start }
    const [selectedMentions, setSelectedMentions] = useState([]); // [{id, name}]
    const textareaRef = useRef(null);
    const fileInputRef = useRef(null);

    const handleFile = async (file) => {
        if (!file) return;
        const form = new FormData();
        form.append("file", file);
        setUploading(true);
        setError("");
        try {
            const { data } = await api.post("/uploads/image", form, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            setAttachments((a) => [...a, { type: data.type, url: data.url, source: "upload" }]);
        } catch (e) {
            setError(getErrorMessage(e));
        } finally {
            setUploading(false);
        }
    };

    const handleGifPick = (gif) => {
        setAttachments((a) => [
            ...a,
            { type: "gif", url: gif.url, width: gif.width, height: gif.height, source: "giphy" },
        ]);
        setGifOpen(false);
    };

    const removeAttachment = (i) => setAttachments((a) => a.filter((_, idx) => idx !== i));

    // Filter users based on current @query
    const mentionCandidates = useMemo(() => {
        if (!mentionQuery) return [];
        const q = mentionQuery.q.toLowerCase();
        return allUsers
            .filter((u) => u.active)
            .filter(
                (u) =>
                    (u.name || "").toLowerCase().includes(q) ||
                    u.email.toLowerCase().startsWith(q)
            )
            .slice(0, 6);
    }, [mentionQuery, allUsers]);

    const onContentChange = (e) => {
        const v = e.target.value;
        setContent(v);
        const pos = e.target.selectionStart ?? v.length;
        // Find the @ token immediately before cursor (no spaces between @ and cursor)
        const upToCursor = v.slice(0, pos);
        const match = /(?:^|\s)@([\w\- .]{0,30})$/.exec(upToCursor);
        if (match) {
            setMentionQuery({ q: match[1].trim(), start: pos - match[1].length - 1 });
        } else {
            setMentionQuery(null);
        }
    };

    const pickMention = (u) => {
        if (!mentionQuery || !textareaRef.current) return;
        const ta = textareaRef.current;
        const pos = ta.selectionStart ?? content.length;
        const before = content.slice(0, mentionQuery.start);
        const after = content.slice(pos);
        const inserted = `@${u.name} `;
        const newContent = `${before}${inserted}${after}`;
        setContent(newContent);
        setSelectedMentions((prev) =>
            prev.some((x) => x.id === u.id) ? prev : [...prev, { id: u.id, name: u.name }]
        );
        setMentionQuery(null);
        requestAnimationFrame(() => {
            const caret = before.length + inserted.length;
            ta.focus();
            ta.setSelectionRange(caret, caret);
        });
    };

    const deriveMentionIds = () => {
        // Keep only mentions whose name is still present in content
        return selectedMentions
            .filter((m) => content.includes(`@${m.name}`))
            .map((m) => m.id);
    };

    const send = async () => {
        if (!channelId) return;
        const trimmed = content.trim();
        if (!trimmed && attachments.length === 0) return;
        setError("");
        try {
            const body = {
                content: trimmed,
                attachments,
                mentions: deriveMentionIds(),
            };
            if (parentId) body.parent_id = parentId;
            const { data } = await api.post(`/messages/channel/${channelId}`, body);
            setContent("");
            setAttachments([]);
            setSelectedMentions([]);
            setMentionQuery(null);
            onSent?.(data);
        } catch (e) {
            setError(getErrorMessage(e));
        }
    };

    const onKeyDown = (e) => {
        if (mentionQuery && mentionCandidates.length > 0) {
            if (e.key === "Enter" || e.key === "Tab") {
                e.preventDefault();
                pickMention(mentionCandidates[0]);
                return;
            }
            if (e.key === "Escape") {
                setMentionQuery(null);
                return;
            }
        }
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    };

    return (
        <div className="border-t border-border bg-white relative" data-testid="message-composer">
            {attachments.length > 0 && (
                <div className="flex gap-2 px-4 pt-3 flex-wrap" data-testid="composer-attachments">
                    {attachments.map((a, i) => {
                        const src = a.url?.startsWith("/")
                            ? `${process.env.REACT_APP_BACKEND_URL}${a.url}`
                            : a.url;
                        return (
                            <div key={i} className="relative border border-border bg-surface">
                                <img src={src} alt={a.type} className="h-20 w-20 object-cover" />
                                <button
                                    className="absolute -top-2 -right-2 w-5 h-5 bg-ink text-white flex items-center justify-center"
                                    onClick={() => removeAttachment(i)}
                                    data-testid={`remove-attachment-${i}`}
                                >
                                    <X className="w-3 h-3" />
                                </button>
                            </div>
                        );
                    })}
                </div>
            )}
            {error && (
                <div className="px-4 py-2 text-xs text-destructive" data-testid="composer-error">
                    {error}
                </div>
            )}
            {mentionQuery && mentionCandidates.length > 0 && (
                <div
                    className="absolute bottom-full left-4 right-4 md:left-16 md:right-auto md:min-w-[280px] mb-1 bg-white border border-ink shadow-lg z-10"
                    data-testid="mention-popover"
                >
                    <div className="ticker-label px-3 py-1.5 bg-surface border-b border-border flex items-center gap-1">
                        <AtSign className="w-3 h-3" /> Mention someone
                    </div>
                    {mentionCandidates.map((u, idx) => (
                        <button
                            key={u.id}
                            onClick={() => pickMention(u)}
                            className={`w-full flex items-center gap-3 p-2 text-left hover:bg-surface ${
                                idx === 0 ? "bg-surface" : ""
                            }`}
                            data-testid={`mention-option-${u.email}`}
                        >
                            <div className="relative shrink-0">
                                <div className="w-7 h-7 bg-ink text-white flex items-center justify-center font-heading font-bold text-xs">
                                    {(u.name || u.email).slice(0, 2).toUpperCase()}
                                </div>
                                <div className="absolute -bottom-0.5 -right-0.5">
                                    <PresenceDot userId={u.id} size="xs" />
                                </div>
                            </div>
                            <div className="min-w-0">
                                <div className="text-sm font-bold truncate">{u.name}</div>
                                <div className="text-xs text-muted-foreground truncate">
                                    {u.email}
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            )}
            <div className="flex items-end gap-2 p-3">
                <div className="flex items-center gap-1">
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => {
                            const f = e.target.files?.[0];
                            handleFile(f);
                            e.target.value = "";
                        }}
                        data-testid="file-input"
                    />
                    <button
                        className="p-2 border border-border hover:border-ink"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={disabled || uploading}
                        data-testid="attach-image-button"
                        title="Attach image / meme"
                    >
                        <ImagePlus className="w-4 h-4" />
                    </button>
                    <button
                        className="p-2 border border-border hover:border-ink"
                        onClick={() => setGifOpen(true)}
                        disabled={disabled}
                        data-testid="open-gif-picker-button"
                        title="Search GIF"
                    >
                        <Smile className="w-4 h-4" />
                    </button>
                </div>
                <textarea
                    ref={textareaRef}
                    value={content}
                    onChange={onContentChange}
                    onKeyDown={onKeyDown}
                    rows={1}
                    placeholder={
                        disabled
                            ? "Select a channel to start chatting…"
                            : parentId
                              ? "Reply to thread…"
                              : "Write a message. @ to mention. Enter to send, Shift+Enter for newline."
                    }
                    className={`flex-1 border border-border focus:border-ink outline-none resize-none px-3 py-2 text-sm bg-white max-h-40 min-h-[42px] ${
                        compact ? "text-sm" : ""
                    }`}
                    disabled={disabled}
                    data-testid={parentId ? "thread-composer-textarea" : "composer-textarea"}
                />
                <button
                    onClick={send}
                    disabled={disabled || uploading || (!content.trim() && attachments.length === 0)}
                    className="btn-signal flex items-center gap-2"
                    data-testid={parentId ? "thread-send-button" : "send-message-button"}
                >
                    <SendHorizontal className="w-4 h-4" />
                    <span className="hidden sm:inline">{parentId ? "Reply" : "Send"}</span>
                </button>
            </div>
            {uploading && (
                <div
                    className="flex items-center gap-2 px-4 pb-2 text-xs text-muted-foreground"
                    data-testid="uploading-indicator"
                >
                    <Paperclip className="w-3 h-3" />
                    Uploading…
                </div>
            )}
            {gifOpen && <GifPicker onClose={() => setGifOpen(false)} onSelect={handleGifPick} />}
        </div>
    );
}
