import React, { useRef, useState } from "react";
import { ImagePlus, Smile, SendHorizontal, X, Paperclip } from "lucide-react";
import { api, getErrorMessage } from "../lib/api";
import GifPicker from "./GifPicker";

export default function MessageComposer({ channelId, disabled, onSent }) {
    const [content, setContent] = useState("");
    const [attachments, setAttachments] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [gifOpen, setGifOpen] = useState(false);
    const [error, setError] = useState("");
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
            setAttachments((a) => [
                ...a,
                { type: data.type, url: data.url, source: "upload" },
            ]);
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

    const send = async () => {
        if (!channelId) return;
        if (!content.trim() && attachments.length === 0) return;
        setError("");
        try {
            const { data } = await api.post(`/messages/channel/${channelId}`, {
                content: content.trim(),
                attachments,
            });
            setContent("");
            setAttachments([]);
            onSent?.(data);
        } catch (e) {
            setError(getErrorMessage(e));
        }
    };

    const onKeyDown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    };

    return (
        <div className="border-t border-border bg-white" data-testid="message-composer">
            {attachments.length > 0 && (
                <div className="flex gap-2 px-4 pt-3 flex-wrap" data-testid="composer-attachments">
                    {attachments.map((a, i) => {
                        const src = a.url?.startsWith("/")
                            ? `${process.env.REACT_APP_BACKEND_URL}${a.url}`
                            : a.url;
                        return (
                            <div key={i} className="relative border border-border bg-surface">
                                <img
                                    src={src}
                                    alt={a.type}
                                    className="h-20 w-20 object-cover"
                                />
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
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    onKeyDown={onKeyDown}
                    rows={1}
                    placeholder={
                        disabled ? "Select a channel to start chatting…" : "Write a message. Enter to send, Shift+Enter for newline."
                    }
                    className="flex-1 border border-border focus:border-ink outline-none resize-none px-3 py-2 text-sm bg-white max-h-40 min-h-[42px]"
                    disabled={disabled}
                    data-testid="composer-textarea"
                />
                <button
                    onClick={send}
                    disabled={disabled || uploading || (!content.trim() && attachments.length === 0)}
                    className="btn-signal flex items-center gap-2"
                    data-testid="send-message-button"
                >
                    <SendHorizontal className="w-4 h-4" />
                    <span className="hidden sm:inline">Send</span>
                </button>
            </div>
            {uploading && (
                <div className="flex items-center gap-2 px-4 pb-2 text-xs text-muted-foreground" data-testid="uploading-indicator">
                    <Paperclip className="w-3 h-3" />
                    Uploading…
                </div>
            )}
            {gifOpen && <GifPicker onClose={() => setGifOpen(false)} onSelect={handleGifPick} />}
        </div>
    );
}
