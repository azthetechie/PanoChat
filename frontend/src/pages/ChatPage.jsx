import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Hash, Lock, Users, Menu } from "lucide-react";
import { api, getErrorMessage } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import ChannelSidebar from "../components/ChannelSidebar";
import MessageList from "../components/MessageList";
import MessageComposer from "../components/MessageComposer";
import CreateChannelDialog from "../components/CreateChannelDialog";
import { useChatSocket } from "../hooks/useChatSocket";

export default function ChatPage() {
    const { user, token } = useAuth();
    const navigate = useNavigate();

    const [channels, setChannels] = useState([]);
    const [activeChannel, setActiveChannel] = useState(null);
    const [messages, setMessages] = useState([]);
    const [loadingMsgs, setLoadingMsgs] = useState(false);
    const [error, setError] = useState("");
    const [createOpen, setCreateOpen] = useState(false);
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [unreadCounts, setUnreadCounts] = useState({});
    const activeChannelRef = useRef(activeChannel);

    useEffect(() => {
        activeChannelRef.current = activeChannel;
    }, [activeChannel]);

    const loadChannels = useCallback(async () => {
        try {
            const { data } = await api.get("/channels");
            setChannels(data);
            if (!activeChannelRef.current && data.length) setActiveChannel(data[0]);
        } catch (e) {
            setError(getErrorMessage(e));
        }
    }, []);

    const loadUnread = useCallback(async () => {
        try {
            const { data } = await api.get("/channels/unread");
            setUnreadCounts(data || {});
        } catch {
            /* non-blocking */
        }
    }, []);

    useEffect(() => {
        loadChannels();
        loadUnread();
    }, [loadChannels, loadUnread]);

    const markChannelRead = useCallback(async (channelId) => {
        if (!channelId) return;
        try {
            await api.post(`/channels/${channelId}/read`);
            setUnreadCounts((prev) => ({ ...prev, [channelId]: 0 }));
        } catch {
            /* ignore */
        }
    }, []);

    const loadMessages = useCallback(
        async (channelId) => {
            if (!channelId) return;
            setLoadingMsgs(true);
            try {
                const { data } = await api.get(`/messages/channel/${channelId}`);
                setMessages(data);
                markChannelRead(channelId);
            } catch (e) {
                setError(getErrorMessage(e));
            } finally {
                setLoadingMsgs(false);
            }
        },
        [markChannelRead]
    );

    useEffect(() => {
        if (activeChannel) loadMessages(activeChannel.id);
        else setMessages([]);
    }, [activeChannel, loadMessages]);

    const handleWsEvent = useCallback(
        (evt) => {
            if (!evt || !evt.type) return;
            if (evt.type === "message:new") {
                const m = evt.message;
                if (!m) return;
                if (activeChannelRef.current?.id === m.channel_id) {
                    setMessages((prev) => (prev.some((x) => x.id === m.id) ? prev : [...prev, m]));
                    // If tab is focused and user is viewing this channel, mark read immediately
                    if (document.visibilityState === "visible") markChannelRead(m.channel_id);
                } else if (m.user_id !== user?.id) {
                    // Increment unread for non-active channel when message is not our own
                    setUnreadCounts((prev) => ({
                        ...prev,
                        [m.channel_id]: (prev[m.channel_id] || 0) + 1,
                    }));
                }
            } else if (evt.type === "message:hidden") {
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === evt.message_id
                            ? {
                                  ...m,
                                  hidden: true,
                                  content:
                                      user?.role === "admin" ? m.content : "[message hidden by admin]",
                                  attachments: user?.role === "admin" ? m.attachments : [],
                              }
                            : m
                    )
                );
            } else if (evt.type === "message:unhidden") {
                const m = evt.message;
                setMessages((prev) => prev.map((x) => (x.id === m.id ? { ...x, ...m } : x)));
            } else if (evt.type === "message:deleted") {
                setMessages((prev) => prev.filter((m) => m.id !== evt.message_id));
            }
        },
        [user?.role, user?.id, markChannelRead]
    );

    const { subscribe, unsubscribe, status } = useChatSocket({
        token,
        onMessage: handleWsEvent,
        enabled: !!user,
    });

    // Subscribe to ALL channels so we receive unread updates even for non-active channels
    useEffect(() => {
        channels.forEach((c) => subscribe(c.id));
        return () => channels.forEach((c) => unsubscribe(c.id));
    }, [channels, subscribe, unsubscribe]);

    // Mark active channel as read when window regains focus
    useEffect(() => {
        const onVis = () => {
            if (document.visibilityState === "visible" && activeChannelRef.current) {
                markChannelRead(activeChannelRef.current.id);
            }
        };
        document.addEventListener("visibilitychange", onVis);
        return () => document.removeEventListener("visibilitychange", onVis);
    }, [markChannelRead]);

    const onMessageSent = (m) => {
        setMessages((prev) => (prev.some((x) => x.id === m.id) ? prev : [...prev, m]));
        if (m.channel_id) markChannelRead(m.channel_id);
    };

    const onMessageUpdated = (m) => {
        if (m?._deleted) {
            setMessages((prev) => prev.filter((x) => x.id !== m.id));
            return;
        }
        setMessages((prev) => prev.map((x) => (x.id === m.id ? { ...x, ...m } : x)));
    };

    const memberCount = useMemo(() => activeChannel?.members?.length || 0, [activeChannel]);

    const selectChannel = (c) => {
        setActiveChannel(c);
        setSidebarOpen(false);
    };

    return (
        <div className="h-[100dvh] h-screen flex bg-white relative" data-testid="chat-page">
            {/* Desktop sidebar */}
            <div className="hidden lg:flex h-full">
                <ChannelSidebar
                    channels={channels}
                    activeChannelId={activeChannel?.id}
                    onSelectChannel={selectChannel}
                    onCreateChannel={() => setCreateOpen(true)}
                    canCreate={user?.role === "admin"}
                    unreadCounts={unreadCounts}
                />
            </div>

            {/* Mobile drawer */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 z-40 lg:hidden"
                    data-testid="sidebar-drawer"
                    onClick={() => setSidebarOpen(false)}
                >
                    <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
                    <div
                        className="absolute inset-y-0 left-0 h-full shadow-2xl animate-in"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <ChannelSidebar
                            channels={channels}
                            activeChannelId={activeChannel?.id}
                            onSelectChannel={selectChannel}
                            onCreateChannel={() => setCreateOpen(true)}
                            canCreate={user?.role === "admin"}
                            unreadCounts={unreadCounts}
                            onClose={() => setSidebarOpen(false)}
                            showCloseButton
                        />
                    </div>
                </div>
            )}

            <main className="flex-1 flex flex-col min-w-0">
                {/* Channel header */}
                <header
                    className="border-b border-border px-4 md:px-6 py-3 md:py-4 flex items-center justify-between gap-3"
                    data-testid="channel-header"
                >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                        <button
                            className="p-2 border border-border hover:border-ink lg:hidden shrink-0"
                            onClick={() => setSidebarOpen(true)}
                            data-testid="open-sidebar-button"
                            aria-label="Open channels"
                        >
                            <Menu className="w-4 h-4" />
                        </button>
                        {activeChannel ? (
                            <>
                                {activeChannel.is_private ? (
                                    <Lock className="w-4 h-4 shrink-0" />
                                ) : (
                                    <Hash className="w-4 h-4 shrink-0" />
                                )}
                                <div className="min-w-0">
                                    <div
                                        className="font-heading font-extrabold text-base md:text-lg tracking-tight truncate"
                                        data-testid="active-channel-name"
                                    >
                                        {activeChannel.name}
                                    </div>
                                    <div className="text-xs text-muted-foreground truncate hidden md:block">
                                        {activeChannel.description || "No description"}
                                    </div>
                                </div>
                            </>
                        ) : (
                            <div className="font-heading font-extrabold text-base md:text-lg tracking-tight">
                                Select a channel
                            </div>
                        )}
                    </div>
                    <div className="flex items-center gap-3 md:gap-4 text-xs text-muted-foreground shrink-0">
                        <div className="flex items-center gap-1">
                            <span
                                className={`w-2 h-2 ${
                                    status === "open" ? "bg-green-600" : "bg-muted-foreground"
                                }`}
                                data-testid="ws-status-dot"
                            />
                            <span className="ticker-label hidden sm:inline">
                                {status === "open" ? "live" : "connecting"}
                            </span>
                        </div>
                        {activeChannel && (
                            <div className="flex items-center gap-1" data-testid="member-count">
                                <Users className="w-3.5 h-3.5" /> {memberCount}
                            </div>
                        )}
                    </div>
                </header>

                {error && (
                    <div
                        className="px-4 md:px-6 py-2 border-b border-border text-xs text-destructive"
                        data-testid="chat-error"
                    >
                        {error}
                    </div>
                )}

                {loadingMsgs ? (
                    <div className="flex-1 flex items-center justify-center text-muted-foreground ticker-label">
                        Loading messages…
                    </div>
                ) : (
                    <MessageList
                        messages={messages}
                        currentUser={user}
                        onMessageUpdated={onMessageUpdated}
                    />
                )}

                <MessageComposer
                    channelId={activeChannel?.id}
                    disabled={!activeChannel || activeChannel.archived}
                    onSent={onMessageSent}
                />
            </main>

            {createOpen && (
                <CreateChannelDialog
                    onClose={() => setCreateOpen(false)}
                    onCreated={(c) => {
                        setCreateOpen(false);
                        setChannels((prev) => [...prev, c]);
                        setActiveChannel(c);
                    }}
                />
            )}
        </div>
    );
}
