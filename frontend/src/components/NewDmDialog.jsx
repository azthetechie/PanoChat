import React, { useEffect, useState } from "react";
import { X, MessageSquarePlus } from "lucide-react";
import { api, getErrorMessage } from "../lib/api";

export default function NewDmDialog({ onClose, onOpened }) {
    const [users, setUsers] = useState([]);
    const [q, setQ] = useState("");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        let ignore = false;
        (async () => {
            try {
                const { data } = await api.get("/users");
                if (!ignore) setUsers(data.filter((u) => u.active));
            } catch (e) {
                if (!ignore) setError(getErrorMessage(e));
            } finally {
                if (!ignore) setLoading(false);
            }
        })();
        return () => {
            ignore = true;
        };
    }, []);

    const start = async (u) => {
        setError("");
        try {
            const { data } = await api.post("/dms", { user_id: u.id });
            onOpened?.(data);
        } catch (e) {
            setError(getErrorMessage(e));
        }
    };

    const filtered = users.filter(
        (u) =>
            (u.name || "").toLowerCase().includes(q.toLowerCase()) ||
            u.email.toLowerCase().includes(q.toLowerCase())
    );

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
            data-testid="new-dm-modal"
            onClick={onClose}
        >
            <div
                className="bg-white border border-ink w-full max-w-md max-h-[80vh] flex flex-col"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between p-4 border-b border-border">
                    <div>
                        <div className="ticker-label text-signal">// DIRECT MESSAGE</div>
                        <div className="font-heading font-extrabold text-xl tracking-tight">
                            Start a conversation
                        </div>
                    </div>
                    <button
                        className="p-2 border border-border hover:border-ink"
                        onClick={onClose}
                        data-testid="new-dm-close"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
                <div className="p-4 border-b border-border">
                    <input
                        autoFocus
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        placeholder="Search teammates…"
                        className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                        data-testid="new-dm-search"
                    />
                </div>
                <div className="overflow-y-auto flex-1">
                    {loading && (
                        <div className="p-6 text-center ticker-label text-muted-foreground">
                            Loading…
                        </div>
                    )}
                    {error && (
                        <div className="p-4 text-sm text-destructive" data-testid="new-dm-error">
                            {error}
                        </div>
                    )}
                    {!loading && filtered.length === 0 && (
                        <div className="p-6 text-center text-sm text-muted-foreground">
                            No teammates match.
                        </div>
                    )}
                    {filtered.map((u) => (
                        <button
                            key={u.id}
                            onClick={() => start(u)}
                            className="w-full flex items-center justify-between gap-3 p-3 border-b border-border hover:bg-surface text-left"
                            data-testid={`new-dm-user-${u.email}`}
                        >
                            <div className="flex items-center gap-3 min-w-0">
                                <div className="w-9 h-9 bg-ink text-white flex items-center justify-center font-heading font-bold text-sm shrink-0">
                                    {(u.name || u.email).slice(0, 2).toUpperCase()}
                                </div>
                                <div className="min-w-0">
                                    <div className="text-sm font-bold truncate">{u.name}</div>
                                    <div className="text-xs text-muted-foreground truncate">
                                        {u.email}
                                    </div>
                                </div>
                            </div>
                            <MessageSquarePlus className="w-4 h-4 text-signal" />
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}
