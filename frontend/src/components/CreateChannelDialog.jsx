import React, { useState } from "react";
import { X } from "lucide-react";
import { api, getErrorMessage } from "../lib/api";

export default function CreateChannelDialog({ onClose, onCreated }) {
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [isPrivate, setIsPrivate] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    const submit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        setError("");
        try {
            const { data } = await api.post("/channels", {
                name: name.trim(),
                description: description.trim(),
                is_private: isPrivate,
            });
            onCreated?.(data);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
            data-testid="create-channel-modal"
            onClick={onClose}
        >
            <form
                onSubmit={submit}
                onClick={(e) => e.stopPropagation()}
                className="bg-white border border-ink w-full max-w-md"
            >
                <div className="flex items-center justify-between p-4 border-b border-border">
                    <div>
                        <div className="ticker-label text-signal">// ADMIN ONLY</div>
                        <div className="font-heading font-extrabold text-xl tracking-tight">
                            Create channel
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="p-2 border border-border hover:border-ink"
                        data-testid="close-create-channel"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
                <div className="p-5 space-y-4">
                    <div>
                        <label className="ticker-label block mb-1">Name</label>
                        <input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="announcements"
                            className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                            required
                            data-testid="channel-name-input"
                        />
                        <div className="ticker-label text-muted-foreground mt-1">
                            lowercase · dashes · no spaces
                        </div>
                    </div>
                    <div>
                        <label className="ticker-label block mb-1">Description</label>
                        <input
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="What is this channel about?"
                            className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                            data-testid="channel-description-input"
                        />
                    </div>
                    <label className="flex items-center gap-2 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={isPrivate}
                            onChange={(e) => setIsPrivate(e.target.checked)}
                            data-testid="channel-private-checkbox"
                        />
                        <span className="text-sm">Private (invite-only)</span>
                    </label>
                    {error && (
                        <div className="border border-destructive text-destructive px-3 py-2 text-xs">
                            {error}
                        </div>
                    )}
                </div>
                <div className="p-4 border-t border-border flex justify-end gap-2">
                    <button
                        type="button"
                        className="btn-ghost"
                        onClick={onClose}
                        data-testid="cancel-create-channel"
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        disabled={submitting}
                        className="btn-signal"
                        data-testid="submit-create-channel"
                    >
                        {submitting ? "Creating…" : "Create channel"}
                    </button>
                </div>
            </form>
        </div>
    );
}
