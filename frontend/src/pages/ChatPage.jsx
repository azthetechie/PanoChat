import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Hash, Lock, Users, Menu, MessageCircle } from "lucide-react";
import { api, getErrorMessage } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import ChannelSidebar from "../components/ChannelSidebar";
import MessageList from "../components/MessageList";
import MessageComposer from "../components/MessageComposer";
import CreateChannelDialog from "../components/CreateChannelDialog";
import NewDmDialog from "../components/NewDmDialog";
import ThreadPanel from "../components/ThreadPanel";
import InstallAppButton from "../components/InstallAppButton";
import { useChatSocket } from "../hooks/useChatSocket";
import { useDesktopNotifications } from "../lib/notifications";
import { usePresence } from "../context/PresenceContext";

export default function ChatPage() {
    const { user, token } = useAuth();
    const navigate = useNavigate();

    const [channels, setChannels] = useState([]);
    const [dms, setDms] = useState([]);
    const [allUsers, setAllUsers] = useState([]);
    const [activeChannel, setActiveChannel] = useState(null);
    const [messages, setMessages] = useState([]);
    const [loadingMsgs, setLoadingMsgs] = useState(false);
    const [error, setError] = useState("");
    const [createOpen, setCreateOpen] = useState(false);
    const [newDmOpen, setNewDmOpen] = useState(false);
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [unreadCounts, setUnreadCounts] = useState({});
    const [threadParent, setThreadParent] = useState(null);
    const [threadReplies, setThreadReplies] = useState([]);
    const activeChannelRef = useRef(activeChannel);
    const threadParentRef = useRef(threadParent);

    useEffect(() => {
        activeChannelRef.current = activeChannel;
    }, [activeChannel]);

    useEffect(() => {
        threadParentRef.current = threadParent;
    }, [threadParent]);

    const loadChannels = useCallback(async () => {
        try {
            const { data } = await api.get("/channels");
            setChannels(data);
            if (!activeChannelRef.current && data.length) setActiveChannel(data[0]);
        } catch (e) {
            setError(getErrorMessage(e));
        }
    }, []);

    const loadDms = useCallback(async () => {
        try {
            const { data } = await api.get("/dms");
            setDms(data);
        } catch {
            /* ignore */
        }
    }, []);

    const loadUsers = useCallback(async () => {
        try {
            const { data } = await api.get("/users");
            setAllUsers(data);
        } catch {
            /* ignore */
        }
    }, []);

    const loadUnread = useCallback(async () => {
        try {
            const { data } = await api.get("/channels/unread");
            setUnreadCounts(data || {});
        } catch {
            /* ignore */
        }
    }, []);

    useEffect(() => {
        loadChannels();
        loadDms();
        loadUsers();
        loadUnread();
    }, [loadChannels, loadDms, loadUsers, loadUnread]);

    const markChannelRead = useCallback(async (channelId) => {
        if (!channelId) return;
        try {
            await api.post(`/channels/${channelId}/read`);
            setUnreadCounts((prev) => ({ ...prev, [channelId]: 0 }));
            setDms((prev) => prev.map((d) => (d.id === channelId ? { ...d, unread: 0 } : d)));
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

    const channelsById = useMemo(() => {
        const map = {};
        channels.forEach((c) => (map[c.id] = { ...c, type: c.type || "channel" }));
        dms.forEach(
            (d) =>
                (map[d.id] = {
                    id: d.id,
                    name: d.other_user_name,
                    type: "dm",
                    members: [user?.id, d.other_user_id],
                    other_user_id: d.other_user_id,
                })
        );
        return map;
    }, [channels, dms, user?.id]);

    const usersById = useMemo(() => {
        const m = {};
        allUsers.forEach((u) => (m[u.id] = u));
        return m;
    }, [allUsers]);

    const { notify } = useDesktopNotifications({
        user,
        channelsById,
        activeChannelId: activeChannel?.id,
    });
    const { applyWsEvent: applyPresenceEvent } = usePresence();

    const handleWsEvent = useCallback(
        (evt) => {
            if (!evt || !evt.type) return;
            if (evt.type === "presence:update") {
                applyPresenceEvent(evt);
                return;
            }
            if (evt.type === "message:new") {
                const m = evt.message;
                if (!m) return;
                const isDm = channelsById[m.channel_id]?.type === "dm";
                if (activeChannelRef.current?.id === m.channel_id) {
                    setMessages((prev) =>
                        prev.some((x) => x.id === m.id) ? prev : [...prev, m]
                    );
                    if (document.visibilityState === "visible") markChannelRead(m.channel_id);
                } else if (m.user_id !== user?.id) {
                    if (isDm) {
                        setDms((prev) =>
                            prev.map((d) =>
                                d.id === m.channel_id
                                    ? {
                                          ...d,
                                          unread: (d.unread || 0) + 1,
                                          last_message_preview: m.content || "[attachment]",
                                          last_message_at: m.created_at,
                                      }
                                    : d
                            )
                        );
                    } else {
                        setUnreadCounts((prev) => ({
                            ...prev,
                            [m.channel_id]: (prev[m.channel_id] || 0) + 1,
                        }));
                    }
                }
                notify(evt);
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
            } else if (evt.type === "message:reactions") {
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === evt.message_id ? { ...m, reactions: evt.reactions } : m
                    )
                );
                setThreadReplies((prev) =>
                    prev.map((m) =>
                        m.id === evt.message_id ? { ...m, reactions: evt.reactions } : m
                    )
                );
                if (threadParentRef.current?.id === evt.message_id) {
                    setThreadParent((p) => (p ? { ...p, reactions: evt.reactions } : p));
                }
            } else if (evt.type === "thread:reply") {
                // Update parent counter in main list
                setMessages((prev) =>
                    prev.map((m) =>
                        m.id === evt.parent_id
                            ? {
                                  ...m,
                                  thread_reply_count: evt.thread_reply_count,
                                  thread_last_reply_at: evt.thread_last_reply_at,
                              }
                            : m
                    )
                );
                // If the user has the thread open, append the reply
                if (threadParentRef.current?.id === evt.parent_id && evt.reply) {
                    setThreadReplies((prev) =>
                        prev.some((x) => x.id === evt.reply.id) ? prev : [...prev, evt.reply]
                    );
                }
                notify({ type: "message:new", message: evt.reply });
            }
        },
        [user?.role, user?.id, markChannelRead, channelsById, notify, applyPresenceEvent]
    );

    const { subscribe, unsubscribe, status } = useChatSocket({
        token,
        onMessage: handleWsEvent,
        enabled: !!user,
    });

    // Subscribe to ALL channels + DMs
    useEffect(() => {
        const ids = [...channels.map((c) => c.id), ...dms.map((d) => d.id)];
        ids.forEach((id) => subscribe(id));
        return () => ids.forEach((id) => unsubscribe(id));
    }, [channels, dms, subscribe, unsubscribe]);

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
        // refresh DMs to update last_message preview
        if (channelsById[m.channel_id]?.type === "dm") loadDms();
    };

    const onMessageUpdated = (m) => {
        if (m?._deleted) {
            setMessages((prev) => prev.filter((x) => x.id !== m.id));
            return;
        }
        setMessages((prev) => prev.map((x) => (x.id === m.id ? { ...x, ...m } : x)));
    };

    const selectChannel = (c) => {
        setActiveChannel({ ...c, type: c.type || "channel" });
        setSidebarOpen(false);
        setThreadParent(null);
        setThreadReplies([]);
    };

    const selectDm = (d) => {
        setActiveChannel({
            id: d.id,
            name: d.other_user_name,
            type: "dm",
            other_user_id: d.other_user_id,
            other_user_email: d.other_user_email,
            members: [user?.id, d.other_user_id],
            archived: false,
        });
        setSidebarOpen(false);
        setThreadParent(null);
        setThreadReplies([]);
    };

    const openThread = (m) => {
        setThreadParent(m);
        setThreadReplies([]);
    };
    const closeThread = () => {
        setThreadParent(null);
        setThreadReplies([]);
    };
    const onThreadReplyPosted = (reply) => {
        setThreadReplies((prev) =>
            prev.some((x) => x.id === reply.id) ? prev : [...prev, reply]
        );
        // Update parent counter in main list
        setMessages((prev) =>
            prev.map((m) =>
                m.id === reply.parent_id
                    ? {
                          ...m,
                          thread_reply_count: (m.thread_reply_count || 0) + 1,
                          thread_last_reply_at: reply.created_at,
                      }
                    : m
            )
        );
    };
    const onThreadLoaded = (replies) => setThreadReplies(replies);

    const handleDmOpened = (dm) => {
        setDms((prev) => (prev.some((d) => d.id === dm.id) ? prev : [dm, ...prev]));
        setNewDmOpen(false);
        selectDm(dm);
    };

    const isDmActive = activeChannel?.type === "dm";
    const memberCount = useMemo(() => activeChannel?.members?.length || 0, [activeChannel]);

    return (
        <div className="h-[100dvh] flex bg-white relative" data-testid="chat-page">
            <div className="hidden lg:flex h-full">
                <ChannelSidebar
                    channels={channels}
                    dms={dms}
                    activeChannelId={activeChannel?.id}
                    onSelectChannel={selectChannel}
                    onSelectDm={selectDm}
                    onCreateChannel={() => setCreateOpen(true)}
                    onNewDm={() => setNewDmOpen(true)}
                    canCreate={user?.role === "admin"}
                    unreadCounts={unreadCounts}
                />
            </div>

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
                            dms={dms}
                            activeChannelId={activeChannel?.id}
                            onSelectChannel={selectChannel}
                            onSelectDm={selectDm}
                            onCreateChannel={() => setCreateOpen(true)}
                            onNewDm={() => setNewDmOpen(true)}
                            canCreate={user?.role === "admin"}
                            unreadCounts={unreadCounts}
                            onClose={() => setSidebarOpen(false)}
                            showCloseButton
                        />
                    </div>
                </div>
            )}

            <main className="flex-1 flex flex-col min-w-0">
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
                                {isDmActive ? (
                                    <MessageCircle className="w-4 h-4 shrink-0" />
                                ) : activeChannel.is_private ? (
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
                                        {isDmActive
                                            ? `Direct message${
                                                  user?.role === "admin" && activeChannel.other_user_email
                                                      ? ` · ${activeChannel.other_user_email}`
                                                      : ""
                                              }`
                                            : activeChannel.description || "No description"}
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
                        <InstallAppButton />
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
                        {activeChannel && !isDmActive && (
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
                        usersById={usersById}
                        onOpenThread={openThread}
                    />
                )}

                <MessageComposer
                    channelId={activeChannel?.id}
                    disabled={!activeChannel || activeChannel.archived}
                    onSent={onMessageSent}
                    allUsers={allUsers}
                />
            </main>

            {/* Thread panel */}
            {threadParent && (
                <>
                    {/* Mobile: full-screen drawer */}
                    <div
                        className="fixed inset-0 z-30 lg:hidden"
                        data-testid="thread-drawer"
                        onClick={closeThread}
                    >
                        <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
                        <div
                            className="absolute inset-y-0 right-0 w-full max-w-md animate-in"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <ThreadPanel
                                parent={threadParent}
                                replies={threadReplies}
                                currentUser={user}
                                allUsers={allUsers}
                                onClose={closeThread}
                                onReplyPosted={onThreadReplyPosted}
                                onReplyLoaded={onThreadLoaded}
                            />
                        </div>
                    </div>
                    {/* Desktop: side panel */}
                    <div className="hidden lg:block h-full">
                        <ThreadPanel
                            parent={threadParent}
                            replies={threadReplies}
                            currentUser={user}
                            allUsers={allUsers}
                            onClose={closeThread}
                            onReplyPosted={onThreadReplyPosted}
                            onReplyLoaded={onThreadLoaded}
                        />
                    </div>
                </>
            )}

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

            {newDmOpen && (
                <NewDmDialog
                    onClose={() => setNewDmOpen(false)}
                    onOpened={handleDmOpened}
                />
            )}
        </div>
    );
}
