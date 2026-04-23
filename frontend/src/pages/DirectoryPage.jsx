import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Search, MessageSquarePlus, Shield, Users } from "lucide-react";
import { api, getErrorMessage } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { usePresence } from "../context/PresenceContext";
import { resolveAssetUrl } from "../context/BrandingContext";

const ROLE_FILTERS = [
    { value: "all", label: "Everyone" },
    { value: "admin", label: "Admins" },
    { value: "user", label: "Members" },
    { value: "online", label: "Active now" },
];

export default function DirectoryPage() {
    const { user } = useAuth();
    const { isOnline } = usePresence();
    const navigate = useNavigate();

    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [q, setQ] = useState("");
    const [filter, setFilter] = useState("all");
    const [starting, setStarting] = useState(null);

    useEffect(() => {
        let ignore = false;
        (async () => {
            try {
                const { data } = await api.get("/users");
                if (!ignore) setUsers((data || []).filter((u) => u.active));
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

    const filtered = useMemo(() => {
        const needle = q.trim().toLowerCase();
        return users
            .filter((u) => {
                if (filter === "admin") return u.role === "admin";
                if (filter === "user") return u.role !== "admin";
                if (filter === "online") return isOnline(u.id);
                return true;
            })
            .filter((u) => {
                if (!needle) return true;
                return (
                    (u.name || "").toLowerCase().includes(needle) ||
                    (u.email || "").toLowerCase().includes(needle)
                );
            })
            .sort((a, b) => {
                // online first, then admins, then name
                const ao = isOnline(a.id) ? 0 : 1;
                const bo = isOnline(b.id) ? 0 : 1;
                if (ao !== bo) return ao - bo;
                const ar = a.role === "admin" ? 0 : 1;
                const br = b.role === "admin" ? 0 : 1;
                if (ar !== br) return ar - br;
                return (a.name || a.email).localeCompare(b.name || b.email);
            });
    }, [users, q, filter, isOnline]);

    const onlineCount = useMemo(
        () => users.filter((u) => isOnline(u.id)).length,
        [users, isOnline]
    );

    const startDm = async (u) => {
        if (u.id === user?.id) return navigate("/profile");
        setStarting(u.id);
        try {
            await api.post("/dms", { user_id: u.id });
            navigate("/");
        } catch (e) {
            setError(getErrorMessage(e));
            setStarting(null);
        }
    };

    return (
        <div className="min-h-screen bg-white" data-testid="directory-page">
            <header className="border-b border-ink">
                <div className="flex items-center justify-between px-4 md:px-10 py-4 md:py-5">
                    <div className="flex items-center gap-3 md:gap-4 min-w-0">
                        <button
                            className="p-2 border border-border hover:border-ink shrink-0"
                            onClick={() => navigate("/")}
                            data-testid="directory-back-button"
                            aria-label="Back to chat"
                        >
                            <ArrowLeft className="w-4 h-4" />
                        </button>
                        <div className="min-w-0">
                            <div className="ticker-label text-signal">// TEAM DIRECTORY</div>
                            <div className="font-heading font-extrabold text-xl md:text-2xl tracking-tight truncate flex items-center gap-3">
                                People
                                <span className="ticker-label text-muted-foreground">
                                    {users.length} · {onlineCount} active
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            <main className="px-4 md:px-10 py-6 md:py-8 max-w-6xl mx-auto">
                <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-4 mb-6">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                            value={q}
                            onChange={(e) => setQ(e.target.value)}
                            placeholder="Search by name or email…"
                            className="w-full border border-border focus:border-ink outline-none pl-10 pr-3 py-2.5 text-sm"
                            data-testid="directory-search-input"
                        />
                    </div>
                    <div className="flex flex-wrap gap-2" data-testid="directory-filters">
                        {ROLE_FILTERS.map((f) => (
                            <button
                                key={f.value}
                                onClick={() => setFilter(f.value)}
                                className={`px-3 py-1.5 border text-xs ticker-label ${
                                    filter === f.value
                                        ? "bg-ink text-white border-ink"
                                        : "border-border hover:border-ink"
                                }`}
                                data-testid={`directory-filter-${f.value}`}
                            >
                                {f.label}
                            </button>
                        ))}
                    </div>
                </div>

                {error && (
                    <div
                        className="mb-4 px-4 py-3 border border-destructive text-destructive text-sm"
                        data-testid="directory-error"
                    >
                        {error}
                    </div>
                )}

                {loading ? (
                    <div className="py-20 text-center ticker-label text-muted-foreground">
                        Loading teammates…
                    </div>
                ) : filtered.length === 0 ? (
                    <div
                        className="py-20 text-center border border-border"
                        data-testid="directory-empty"
                    >
                        <Users className="w-8 h-8 mx-auto mb-3 text-muted-foreground" />
                        <div className="ticker-label text-muted-foreground">
                            No teammates match your filters.
                        </div>
                    </div>
                ) : (
                    <div
                        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4"
                        data-testid="directory-grid"
                    >
                        {filtered.map((u) => (
                            <PersonCard
                                key={u.id}
                                person={u}
                                isMe={u.id === user?.id}
                                online={isOnline(u.id)}
                                starting={starting === u.id}
                                onStart={() => startDm(u)}
                            />
                        ))}
                    </div>
                )}
            </main>
        </div>
    );
}

function PersonCard({ person, isMe, online, starting, onStart }) {
    const avatarUrl = resolveAssetUrl(person.avatar_url);
    const initials = (person.name || person.email).slice(0, 2).toUpperCase();
    return (
        <div
            className="border border-border hover:border-ink transition-colors bg-white p-4 flex flex-col gap-3"
            data-testid={`directory-card-${person.email}`}
        >
            <div className="flex items-start gap-3">
                <div className="relative shrink-0">
                    {avatarUrl ? (
                        <img
                            src={avatarUrl}
                            alt={person.name}
                            className="w-12 h-12 object-cover border border-border"
                        />
                    ) : (
                        <div className="w-12 h-12 bg-ink text-white flex items-center justify-center font-heading font-bold text-base">
                            {initials}
                        </div>
                    )}
                    <div
                        className={`absolute -bottom-1 -right-1 w-3.5 h-3.5 border-2 border-white ${
                            online ? "bg-green-600" : "bg-muted-foreground"
                        }`}
                        data-testid={`directory-presence-${person.email}`}
                        title={online ? "Active now" : "Offline"}
                    />
                </div>
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                        <div
                            className="font-heading font-extrabold tracking-tight truncate"
                            data-testid={`directory-name-${person.email}`}
                        >
                            {person.name || "—"}
                        </div>
                        {person.role === "admin" && (
                            <span className="inline-flex items-center gap-1 bg-signal text-white text-[10px] uppercase tracking-wider px-1.5 py-0.5 font-heading font-bold">
                                <Shield className="w-3 h-3" /> Admin
                            </span>
                        )}
                        {isMe && (
                            <span className="text-[10px] uppercase tracking-wider border border-border px-1.5 py-0.5 text-muted-foreground">
                                You
                            </span>
                        )}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">{person.email}</div>
                    <div className="mt-1 text-[11px] ticker-label text-muted-foreground">
                        {online ? "● active now" : "○ offline"}
                    </div>
                </div>
            </div>
            <div className="flex items-center justify-end gap-2 pt-1 border-t border-border mt-1">
                <button
                    onClick={onStart}
                    disabled={starting}
                    className={isMe ? "btn-ghost text-xs" : "btn-signal text-xs flex items-center gap-2"}
                    data-testid={isMe ? `directory-edit-profile-${person.email}` : `directory-start-dm-${person.email}`}
                >
                    {isMe ? (
                        "Edit my profile"
                    ) : (
                        <>
                            <MessageSquarePlus className="w-3.5 h-3.5" />
                            {starting ? "Opening…" : "Message"}
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}
