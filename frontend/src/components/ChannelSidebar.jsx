import React from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Hash, Lock, Archive, Plus, Shield, LogOut, User, UserCog } from "lucide-react";

export default function ChannelSidebar({
    channels,
    activeChannelId,
    onSelectChannel,
    onCreateChannel,
    canCreate = false,
}) {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    return (
        <aside
            className="w-72 bg-sidebar border-r border-border flex flex-col h-full"
            data-testid="channel-sidebar"
        >
            <div className="p-5 border-b border-border">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 bg-ink flex items-center justify-center">
                        <div className="w-2.5 h-2.5 bg-signal" />
                    </div>
                    <div className="leading-tight">
                        <div className="font-heading font-extrabold text-sm tracking-tight">
                            PANORAMA / COMMS
                        </div>
                        <div className="ticker-label text-muted-foreground">Self-hosted</div>
                    </div>
                </div>
            </div>

            <div className="flex items-center justify-between px-5 pt-5 pb-2">
                <div className="ticker-label">Channels</div>
                {canCreate && (
                    <button
                        className="p-1 border border-border hover:border-ink transition-colors"
                        onClick={onCreateChannel}
                        data-testid="create-channel-button"
                        title="New channel"
                    >
                        <Plus className="w-3.5 h-3.5" />
                    </button>
                )}
            </div>

            <nav className="flex-1 overflow-y-auto" data-testid="channel-list">
                {channels.length === 0 && (
                    <div className="px-5 py-6 text-sm text-muted-foreground" data-testid="channels-empty">
                        No channels yet.
                    </div>
                )}
                {channels.map((c) => {
                    const active = c.id === activeChannelId;
                    const Icon = c.archived ? Archive : c.is_private ? Lock : Hash;
                    return (
                        <button
                            key={c.id}
                            onClick={() => onSelectChannel(c)}
                            className={`w-full text-left px-5 py-2.5 flex items-center gap-2 border-l-4 transition-colors ${
                                active
                                    ? "bg-white border-l-signal text-ink font-bold"
                                    : "border-l-transparent text-muted-foreground hover:bg-white/60 hover:text-ink"
                            }`}
                            data-testid={`channel-item-${c.name}`}
                        >
                            <Icon className="w-4 h-4 shrink-0" />
                            <span className="truncate">{c.name}</span>
                            {c.archived && (
                                <span className="ml-auto ticker-label text-muted-foreground">
                                    archived
                                </span>
                            )}
                        </button>
                    );
                })}
            </nav>

            <div className="border-t border-border p-4 space-y-2">
                {user?.role === "admin" && (
                    <button
                        className="btn-ghost w-full flex items-center justify-center gap-2"
                        onClick={() => navigate("/admin")}
                        data-testid="open-admin-button"
                    >
                        <Shield className="w-4 h-4" />
                        Admin console
                    </button>
                )}
                <button
                    className="btn-ghost w-full flex items-center justify-center gap-2"
                    onClick={() => navigate("/profile")}
                    data-testid="open-profile-button"
                >
                    <UserCog className="w-4 h-4" />
                    Profile & security
                </button>
                <div className="flex items-center gap-3 px-1 pt-1">
                    <div className="w-8 h-8 bg-ink text-white flex items-center justify-center">
                        <User className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="text-sm font-bold truncate" data-testid="sidebar-user-name">
                            {user?.name}
                        </div>
                        <div className="text-xs text-muted-foreground truncate">
                            {user?.role === "admin" ? "Administrator" : "Member"}
                        </div>
                    </div>
                    <button
                        className="p-2 border border-border hover:border-destructive hover:text-destructive transition-colors"
                        onClick={async () => {
                            await logout();
                            navigate("/login");
                        }}
                        data-testid="logout-button"
                        title="Log out"
                    >
                        <LogOut className="w-4 h-4" />
                    </button>
                </div>
            </div>
        </aside>
    );
}
