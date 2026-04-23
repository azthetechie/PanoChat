import React, { useEffect, useState } from "react";
import { X, Search } from "lucide-react";
import { api, getErrorMessage } from "../lib/api";

export default function GifPicker({ onClose, onSelect }) {
    const [q, setQ] = useState("");
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const load = async (query = "") => {
        setLoading(true);
        setError("");
        try {
            const endpoint = query ? `/giphy/search?q=${encodeURIComponent(query)}&limit=24` : "/giphy/trending?limit=24";
            const { data } = await api.get(endpoint);
            setResults(data.results || []);
        } catch (e) {
            setError(getErrorMessage(e));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    useEffect(() => {
        const t = setTimeout(() => {
            load(q.trim());
        }, 300);
        return () => clearTimeout(t);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [q]);

    return (
        <div
            className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/40 backdrop-blur-sm"
            data-testid="gif-picker-modal"
            onClick={onClose}
        >
            <div
                className="bg-white border border-ink w-full max-w-xl max-h-[80vh] flex flex-col shadow-2xl"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between p-4 border-b border-border">
                    <div>
                        <div className="ticker-label text-signal">// POWERED BY GIPHY</div>
                        <div className="font-heading font-extrabold text-xl tracking-tight">
                            Search a GIF
                        </div>
                    </div>
                    <button
                        className="p-2 border border-border hover:border-ink"
                        onClick={onClose}
                        data-testid="gif-picker-close"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
                <div className="px-4 py-3 border-b border-border flex items-center gap-2">
                    <Search className="w-4 h-4" />
                    <input
                        autoFocus
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        placeholder="Search memes, reactions, moods…"
                        className="flex-1 border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                        data-testid="gif-search-input"
                    />
                </div>
                <div className="flex-1 overflow-y-auto p-3">
                    {loading && (
                        <div className="text-center py-8 ticker-label text-muted-foreground">
                            Loading…
                        </div>
                    )}
                    {error && (
                        <div className="text-center py-8 text-destructive text-sm" data-testid="gif-error">
                            {error}
                        </div>
                    )}
                    {!loading && !error && results.length === 0 && (
                        <div className="text-center py-8 text-sm text-muted-foreground">
                            No results.
                        </div>
                    )}
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2" data-testid="gif-grid">
                        {results.map((r) => (
                            <button
                                key={r.id}
                                onClick={() => onSelect(r)}
                                className="group relative overflow-hidden border border-border hover:border-ink transition-colors bg-surface"
                                data-testid={`gif-item-${r.id}`}
                            >
                                <img
                                    src={r.preview_url || r.url}
                                    alt={r.title}
                                    className="w-full h-28 object-cover"
                                    loading="lazy"
                                />
                            </button>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
