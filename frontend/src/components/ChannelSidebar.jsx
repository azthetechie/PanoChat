import React from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useBranding, resolveAssetUrl } from "../context/BrandingContext";
import {
    Hash,
    Lock,
    Archive,
    Plus,
    Shield,
    LogOut,
    User,
    UserCog,
    X,
    MessageSquarePlus,
} from "lucide-react";

export default function ChannelSidebar({
    channels,
    dms = [],
    activeChannelId,
    onSelectChannel,
    onSelectDm,
    onCreateChannel,
    onNewDm,
    canCreate = false,
    unreadCounts = {},
    onClose,
    showCloseButton = false,
}) {
    const { user, logout } = useAuth();
    const { branding } = useBranding();
    const navigate = useNavigate();
    const logoUrl = resolveAssetUrl(branding.logo_url);

    return (
        <aside
            className="w-72 max-w-[85vw] bg-sidebar border-r border-border flex flex-col h-full"
            data-testid="channel-sidebar"
        >
            <div className="p-5 border-b border-border flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                    {logoUrl ? (
                        <img
                            src={logoUrl}
                            alt="logo"
                            className="w-9 h-9 object-contain border border-border bg-white shrink-0"
                            data-testid="sidebar-brand-logo"
                        />
                    ) : (
                        <div className="w-9 h-9 bg-ink flex items-center justify-center shrink-0">
                            <div className="w-2.5 h-2.5 bg-signal" />
                        </div>
                    )}
                    <div className="leading-tight min-w-0">
                        <div className="font-heading font-extrabold text-sm tracking-tight truncate">
                            {branding.brand_name || "PANORAMA / COMMS"}
                        </div>
                        <div className="ticker-label text-muted-foreground truncate">
                            {branding.tagline || "Self-hosted"}
                        </div>
                    </div>
                </div>
                {showCloseButton && (
                    <button
                        className="p-1.5 border border-border hover:border-ink lg:hidden"
                        onClick={onClose}
                        data-testid="sidebar-close-button"
                        aria-label="Close sidebar"
                    >
                        <X className="w-4 h-4" />
                    </button>
                )}
            </div>

            <nav className="flex-1 overflow-y-auto" data-testid="channel-list">
                {/* Channels */}
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

                {channels.length === 0 && (
                    <div className="px-5 py-3 text-sm text-muted-foreground" data-testid="channels-empty">
                        No channels yet.
                    </div>
                )}
                {channels.map((c) => {
                    const active = c.id === activeChannelId;
                    const unread = unreadCounts[c.id] || 0;
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
                            <span className={`truncate flex-1 ${unread > 0 && !active ? "text-ink font-bold" : ""}`}>
                                {c.name}
                            </span>
                            {unread > 0 && (
                                <span
                                    className="bg-signal text-white text-xs font-bold px-1.5 min-w-[1.25rem] h-5 flex items-center justify-center leading-none"
                                    data-testid={`unread-badge-${c.name}`}
                                >
                                    {unread > 99 ? "99+" : unread}
                                </span>
                            )}
                        </button>
                    );
                })}

                {/* Direct Messages */}
                <div className="flex items-center justify-between px-5 pt-6 pb-2">
                    <div className="ticker-label">Direct Messages</div>
                    <button
                        className="p-1 border border-border hover:border-ink transition-colors"
                        onClick={onNewDm}
                        data-testid="new-dm-button"
                        title="New direct message"
                    >
                        <MessageSquarePlus className="w-3.5 h-3.5" />
                    </button>
                </div>
                {dms.length === 0 && (
                    <div className="px-5 py-3 text-sm text-muted-foreground" data-testid="dms-empty">
                        No conversations yet.
                    </div>
                )}
                {dms.map((d) => {
                    const active = d.id === activeChannelId;
                    const unread = d.unread || 0;
                    const initials = (d.other_user_name || d.other_user_email || "?")
                        .split(" ")
                        .map((p) => p[0])
                        .filter(Boolean)
                        .slice(0, 2)
                        .join("")
                        .toUpperCase();
                    return (
                        <button
                            key={d.id}
                            onClick={() => onSelectDm(d)}
                            className={`w-full text-left px-5 py-2.5 flex items-center gap-3 border-l-4 transition-colors ${
                                active
                                    ? "bg-white border-l-signal text-ink font-bold"
                                    : "border-l-transparent text-muted-foreground hover:bg-white/60 hover:text-ink"
                            }`}
                            data-testid={`dm-item-${d.other_user_email}`}
                        >
                            <div className="w-7 h-7 bg-ink text-white flex items-center justify-center font-heading font-bold text-xs shrink-0">
                                {initials}
                            </div>
                            <span className={`truncate flex-1 ${unread > 0 && !active ? "text-ink font-bold" : ""}`}>
                                {d.other_user_name}
                            </span>
                            {unread > 0 && (
                                <span
                                    className="bg-signal text-white text-xs font-bold px-1.5 min-w-[1.25rem] h-5 flex items-center justify-center leading-none"
                                    data-testid={`dm-unread-${d.other_user_email}`}
                                >
                                    {unread > 99 ? "99+" : unread}
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
