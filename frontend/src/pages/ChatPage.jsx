import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Hash, Lock, Users } from "lucide-react";
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
    const activeChannelRef = useRef(activeChannel);

    useEffect(() => {
        activeChannelRef.current = activeChannel;
    }, [activeChannel]);

    const loadChannels = useCallback(async () => {
        try {
            const { data } = await api.get("/channels");
            setChannels(data);
            if (!activeChannelRef.current && data.length) {
                setActiveChannel(data[0]);
            }
        } catch (e) {
            setError(getErrorMessage(e));
        }
    }, []);

    useEffect(() => {
        loadChannels();
    }, [loadChannels]);

    const loadMessages = useCallback(async (channelId) => {
        if (!channelId) return;
        setLoadingMsgs(true);
        try {
            const { data } = await api.get(`/messages/channel/${channelId}`);
            setMessages(data);
        } catch (e) {
            setError(getErrorMessage(e));
        } finally {
            setLoadingMsgs(false);
        }
    }, []);

    useEffect(() => {
        if (activeChannel) {
            loadMessages(activeChannel.id);
        } else {
            setMessages([]);
        }
    }, [activeChannel, loadMessages]);

    const handleWsEvent = useCallback((evt) => {
        if (!evt || !evt.type) return;
        if (evt.type === "message:new") {
            const m = evt.message;
            if (!m) return;
            if (activeChannelRef.current?.id === m.channel_id) {
                setMessages((prev) => {
                    if (prev.some((x) => x.id === m.id)) return prev;
                    return [...prev, m];
                });
            }
        } else if (evt.type === "message:hidden") {
            setMessages((prev) =>
                prev.map((m) =>
                    m.id === evt.message_id
                        ? {
                              ...m,
                              hidden: true,
                              content: user?.role === "admin" ? m.content : "[message hidden by admin]",
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
    }, [user?.role]);

    const { subscribe, unsubscribe, status } = useChatSocket({
        token,
        onMessage: handleWsEvent,
        enabled: !!user,
    });

    useEffect(() => {
        if (!activeChannel) return;
        subscribe(activeChannel.id);
        const id = activeChannel.id;
        return () => unsubscribe(id);
    }, [activeChannel, subscribe, unsubscribe]);

    const onMessageSent = (m) => {
        setMessages((prev) => (prev.some((x) => x.id === m.id) ? prev : [...prev, m]));
    };

    const onMessageUpdated = (m) => {
        if (m?._deleted) {
            setMessages((prev) => prev.filter((x) => x.id !== m.id));
            return;
        }
        setMessages((prev) => prev.map((x) => (x.id === m.id ? { ...x, ...m } : x)));
    };

    const memberCount = useMemo(() => activeChannel?.members?.length || 0, [activeChannel]);

    return (
        <div className="h-screen flex bg-white" data-testid="chat-page">
            <ChannelSidebar
                channels={channels}
                activeChannelId={activeChannel?.id}
                onSelectChannel={setActiveChannel}
                onCreateChannel={() => setCreateOpen(true)}
                canCreate={user?.role === "admin"}
            />
            <main className="flex-1 flex flex-col min-w-0">
                {/* Channel header */}
                <header className="border-b border-border px-6 py-4 flex items-center justify-between" data-testid="channel-header">
                    <div className="flex items-center gap-3 min-w-0">
                        {activeChannel ? (
                            <>
                                {activeChannel.is_private ? (
                                    <Lock className="w-4 h-4 shrink-0" />
                                ) : (
                                    <Hash className="w-4 h-4 shrink-0" />
                                )}
                                <div className="min-w-0">
                                    <div className="font-heading font-extrabold text-lg tracking-tight truncate" data-testid="active-channel-name">
                                        {activeChannel.name}
                                    </div>
                                    <div className="text-xs text-muted-foreground truncate">
                                        {activeChannel.description || "No description"}
                                    </div>
                                </div>
                            </>
                        ) : (
                            <div className="font-heading font-extrabold text-lg tracking-tight">
                                Select a channel
                            </div>
                        )}
                    </div>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <div className="flex items-center gap-1">
                            <span
                                className={`w-2 h-2 ${
                                    status === "open" ? "bg-green-600" : "bg-muted-foreground"
                                }`}
                                data-testid="ws-status-dot"
                            />
                            <span className="ticker-label">
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
                    <div className="px-6 py-2 border-b border-border text-xs text-destructive" data-testid="chat-error">
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
