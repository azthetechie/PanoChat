import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, getErrorMessage } from "../lib/api";
import { ArrowLeft, Plus, Trash2, Shield, UserX, UserCheck, Eye, EyeOff, Users as UsersIcon, Hash, MessageSquare } from "lucide-react";

export default function AdminPage() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [tab, setTab] = useState("users");

    if (user && user.role !== "admin") {
        navigate("/", { replace: true });
    }

    return (
        <div className="min-h-screen bg-white" data-testid="admin-page">
            <header className="border-b border-ink">
                <div className="flex items-center justify-between px-6 md:px-10 py-5">
                    <div className="flex items-center gap-4">
                        <button
                            className="p-2 border border-border hover:border-ink"
                            onClick={() => navigate("/")}
                            data-testid="back-to-chat-button"
                        >
                            <ArrowLeft className="w-4 h-4" />
                        </button>
                        <div>
                            <div className="ticker-label text-signal">// ADMIN CONSOLE</div>
                            <div className="font-heading font-extrabold text-2xl tracking-tight">
                                Panorama Comms — Control
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="text-sm hidden md:block">
                            <div className="font-bold">{user?.name}</div>
                            <div className="text-xs text-muted-foreground">{user?.email}</div>
                        </div>
                        <button
                            className="btn-ghost"
                            onClick={async () => {
                                await logout();
                                navigate("/login");
                            }}
                            data-testid="admin-logout-button"
                        >
                            Log out
                        </button>
                    </div>
                </div>
                <nav className="flex gap-px bg-border">
                    {[
                        { id: "users", label: "Users", icon: UsersIcon },
                        { id: "channels", label: "Channels", icon: Hash },
                        { id: "moderation", label: "Moderation", icon: MessageSquare },
                    ].map((t) => {
                        const Icon = t.icon;
                        const active = t.id === tab;
                        return (
                            <button
                                key={t.id}
                                onClick={() => setTab(t.id)}
                                className={`flex items-center gap-2 px-5 py-3 bg-white ${
                                    active
                                        ? "border-t-4 border-t-signal text-ink font-bold"
                                        : "border-t-4 border-t-transparent text-muted-foreground hover:text-ink"
                                }`}
                                data-testid={`admin-tab-${t.id}`}
                            >
                                <Icon className="w-4 h-4" />
                                {t.label}
                            </button>
                        );
                    })}
                </nav>
            </header>

            <main className="px-6 md:px-10 py-8">
                {tab === "users" && <UsersTab />}
                {tab === "channels" && <ChannelsTab />}
                {tab === "moderation" && <ModerationTab />}
            </main>
        </div>
    );
}

function UsersTab() {
    const { user } = useAuth();
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [formOpen, setFormOpen] = useState(false);

    const load = async () => {
        setLoading(true);
        setError("");
        try {
            const { data } = await api.get("/users");
            setUsers(data);
        } catch (e) {
            setError(getErrorMessage(e));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    const updateUser = async (u, patch) => {
        try {
            const { data } = await api.patch(`/users/${u.id}`, patch);
            setUsers((prev) => prev.map((x) => (x.id === u.id ? data : x)));
        } catch (e) {
            alert(getErrorMessage(e));
        }
    };

    const deleteUser = async (u) => {
        if (!window.confirm(`Delete ${u.email}? This cannot be undone.`)) return;
        try {
            await api.delete(`/users/${u.id}`);
            setUsers((prev) => prev.filter((x) => x.id !== u.id));
        } catch (e) {
            alert(getErrorMessage(e));
        }
    };

    return (
        <section data-testid="users-tab">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="font-heading font-extrabold text-3xl tracking-tight">Users</h2>
                    <p className="text-muted-foreground text-sm">Manage who has access to Panorama Comms.</p>
                </div>
                <button
                    className="btn-signal flex items-center gap-2"
                    onClick={() => setFormOpen(true)}
                    data-testid="open-create-user-button"
                >
                    <Plus className="w-4 h-4" /> New user
                </button>
            </div>

            {error && (
                <div className="border border-destructive text-destructive px-3 py-2 mb-4 text-sm" data-testid="users-error">
                    {error}
                </div>
            )}

            <div className="border border-border overflow-x-auto">
                <table className="w-full border-collapse text-sm" data-testid="users-table">
                    <thead className="bg-sidebar">
                        <tr>
                            {["Name", "Email", "Role", "Status", "Created", ""].map((h) => (
                                <th
                                    key={h}
                                    className="text-left ticker-label text-muted-foreground p-4 border-b border-border"
                                >
                                    {h}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan={6} className="p-6 text-center text-muted-foreground">
                                    Loading…
                                </td>
                            </tr>
                        ) : users.length === 0 ? (
                            <tr>
                                <td colSpan={6} className="p-6 text-center text-muted-foreground">
                                    No users yet.
                                </td>
                            </tr>
                        ) : (
                            users.map((u) => (
                                <tr
                                    key={u.id}
                                    className="border-b border-border hover:bg-surface"
                                    data-testid={`user-row-${u.email}`}
                                >
                                    <td className="p-4 font-bold">{u.name}</td>
                                    <td className="p-4 text-muted-foreground">{u.email}</td>
                                    <td className="p-4">
                                        <span
                                            className={`ticker-label px-2 py-1 border ${
                                                u.role === "admin"
                                                    ? "border-signal text-signal"
                                                    : "border-border"
                                            }`}
                                        >
                                            {u.role}
                                        </span>
                                    </td>
                                    <td className="p-4">
                                        <span
                                            className={`ticker-label ${
                                                u.active ? "text-green-700" : "text-destructive"
                                            }`}
                                        >
                                            {u.active ? "active" : "deactivated"}
                                        </span>
                                    </td>
                                    <td className="p-4 text-xs text-muted-foreground">
                                        {new Date(u.created_at).toLocaleDateString()}
                                    </td>
                                    <td className="p-4">
                                        <div className="flex items-center gap-2 justify-end">
                                            {u.id !== user.id && (
                                                <>
                                                    <button
                                                        className="btn-ghost text-xs px-2 py-1"
                                                        onClick={() =>
                                                            updateUser(u, {
                                                                role: u.role === "admin" ? "user" : "admin",
                                                            })
                                                        }
                                                        data-testid={`toggle-role-${u.email}`}
                                                    >
                                                        <Shield className="w-3 h-3 inline mr-1" />
                                                        {u.role === "admin" ? "Demote" : "Promote"}
                                                    </button>
                                                    <button
                                                        className="btn-ghost text-xs px-2 py-1"
                                                        onClick={() => updateUser(u, { active: !u.active })}
                                                        data-testid={`toggle-active-${u.email}`}
                                                    >
                                                        {u.active ? (
                                                            <>
                                                                <UserX className="w-3 h-3 inline mr-1" /> Deactivate
                                                            </>
                                                        ) : (
                                                            <>
                                                                <UserCheck className="w-3 h-3 inline mr-1" /> Activate
                                                            </>
                                                        )}
                                                    </button>
                                                    <button
                                                        className="btn-ghost text-xs px-2 py-1 hover:border-destructive hover:text-destructive"
                                                        onClick={() => deleteUser(u)}
                                                        data-testid={`delete-user-${u.email}`}
                                                    >
                                                        <Trash2 className="w-3 h-3" />
                                                    </button>
                                                </>
                                            )}
                                            {u.id === user.id && (
                                                <span className="ticker-label text-muted-foreground">you</span>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
            {formOpen && (
                <CreateUserDialog
                    onClose={() => setFormOpen(false)}
                    onCreated={(u) => {
                        setUsers((prev) => [...prev, u]);
                        setFormOpen(false);
                    }}
                />
            )}
        </section>
    );
}

function CreateUserDialog({ onClose, onCreated }) {
    const [form, setForm] = useState({ name: "", email: "", password: "", role: "user" });
    const [error, setError] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const submit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        setError("");
        try {
            const { data } = await api.post("/users", {
                name: form.name.trim(),
                email: form.email.trim().toLowerCase(),
                password: form.password,
                role: form.role,
            });
            onCreated(data);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSubmitting(false);
        }
    };
    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
            onClick={onClose}
            data-testid="create-user-modal"
        >
            <form
                onSubmit={submit}
                onClick={(e) => e.stopPropagation()}
                className="bg-white border border-ink w-full max-w-md"
            >
                <div className="p-4 border-b border-border">
                    <div className="ticker-label text-signal">// NEW MEMBER</div>
                    <div className="font-heading font-extrabold text-xl tracking-tight">Create user</div>
                </div>
                <div className="p-5 space-y-4">
                    <Input
                        label="Name"
                        value={form.name}
                        onChange={(v) => setForm({ ...form, name: v })}
                        testid="new-user-name-input"
                        required
                    />
                    <Input
                        label="Email"
                        type="email"
                        value={form.email}
                        onChange={(v) => setForm({ ...form, email: v })}
                        testid="new-user-email-input"
                        required
                    />
                    <Input
                        label="Password"
                        type="password"
                        value={form.password}
                        onChange={(v) => setForm({ ...form, password: v })}
                        testid="new-user-password-input"
                        required
                        minLength={6}
                    />
                    <div>
                        <label className="ticker-label block mb-1">Role</label>
                        <select
                            value={form.role}
                            onChange={(e) => setForm({ ...form, role: e.target.value })}
                            className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm bg-white"
                            data-testid="new-user-role-select"
                        >
                            <option value="user">user</option>
                            <option value="admin">admin</option>
                        </select>
                    </div>
                    {error && (
                        <div className="border border-destructive text-destructive px-3 py-2 text-xs">
                            {error}
                        </div>
                    )}
                </div>
                <div className="p-4 border-t border-border flex justify-end gap-2">
                    <button type="button" className="btn-ghost" onClick={onClose} data-testid="cancel-create-user">
                        Cancel
                    </button>
                    <button type="submit" disabled={submitting} className="btn-signal" data-testid="submit-create-user">
                        {submitting ? "Creating…" : "Create"}
                    </button>
                </div>
            </form>
        </div>
    );
}

function Input({ label, value, onChange, type = "text", required, testid, minLength }) {
    return (
        <div>
            <label className="ticker-label block mb-1">{label}</label>
            <input
                type={type}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                required={required}
                minLength={minLength}
                className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                data-testid={testid}
            />
        </div>
    );
}

// ----- Channels -----
function ChannelsTab() {
    const [channels, setChannels] = useState([]);
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [createOpen, setCreateOpen] = useState(false);
    const [membersOpen, setMembersOpen] = useState(null);

    const load = async () => {
        setLoading(true);
        try {
            const [c, u] = await Promise.all([api.get("/channels"), api.get("/users")]);
            setChannels(c.data);
            setUsers(u.data);
        } catch (e) {
            setError(getErrorMessage(e));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    const update = async (c, patch) => {
        try {
            const { data } = await api.patch(`/channels/${c.id}`, patch);
            setChannels((prev) => prev.map((x) => (x.id === c.id ? data : x)));
        } catch (e) {
            alert(getErrorMessage(e));
        }
    };

    const del = async (c) => {
        if (!window.confirm(`Delete #${c.name}? All messages will be removed.`)) return;
        try {
            await api.delete(`/channels/${c.id}`);
            setChannels((prev) => prev.filter((x) => x.id !== c.id));
        } catch (e) {
            alert(getErrorMessage(e));
        }
    };

    return (
        <section data-testid="channels-tab">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="font-heading font-extrabold text-3xl tracking-tight">Channels</h2>
                    <p className="text-muted-foreground text-sm">Create, archive, delete and manage members.</p>
                </div>
                <button
                    className="btn-signal flex items-center gap-2"
                    onClick={() => setCreateOpen(true)}
                    data-testid="admin-new-channel-button"
                >
                    <Plus className="w-4 h-4" /> New channel
                </button>
            </div>
            {error && <div className="text-destructive text-sm mb-4">{error}</div>}
            <div className="border border-border overflow-x-auto">
                <table className="w-full border-collapse text-sm" data-testid="channels-table">
                    <thead className="bg-sidebar">
                        <tr>
                            {["Name", "Type", "Description", "Members", "Status", ""].map((h) => (
                                <th key={h} className="text-left ticker-label text-muted-foreground p-4 border-b border-border">
                                    {h}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan={6} className="p-6 text-center text-muted-foreground">
                                    Loading…
                                </td>
                            </tr>
                        ) : (
                            channels.map((c) => (
                                <tr
                                    key={c.id}
                                    className="border-b border-border hover:bg-surface"
                                    data-testid={`channel-row-${c.name}`}
                                >
                                    <td className="p-4 font-bold">#{c.name}</td>
                                    <td className="p-4">
                                        <span className="ticker-label">{c.is_private ? "private" : "public"}</span>
                                    </td>
                                    <td className="p-4 text-muted-foreground max-w-xs truncate">
                                        {c.description || "—"}
                                    </td>
                                    <td className="p-4">{c.members?.length || 0}</td>
                                    <td className="p-4">
                                        <span className={`ticker-label ${c.archived ? "text-destructive" : "text-green-700"}`}>
                                            {c.archived ? "archived" : "active"}
                                        </span>
                                    </td>
                                    <td className="p-4">
                                        <div className="flex items-center gap-2 justify-end">
                                            <button
                                                className="btn-ghost text-xs px-2 py-1"
                                                onClick={() => setMembersOpen(c)}
                                                data-testid={`manage-members-${c.name}`}
                                            >
                                                Members
                                            </button>
                                            <button
                                                className="btn-ghost text-xs px-2 py-1"
                                                onClick={() => update(c, { archived: !c.archived })}
                                                data-testid={`toggle-archive-${c.name}`}
                                            >
                                                {c.archived ? "Unarchive" : "Archive"}
                                            </button>
                                            <button
                                                className="btn-ghost text-xs px-2 py-1 hover:border-destructive hover:text-destructive"
                                                onClick={() => del(c)}
                                                data-testid={`delete-channel-${c.name}`}
                                            >
                                                <Trash2 className="w-3 h-3" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
            {createOpen && (
                <AdminCreateChannel
                    onClose={() => setCreateOpen(false)}
                    onCreated={(c) => {
                        setChannels((prev) => [...prev, c]);
                        setCreateOpen(false);
                    }}
                />
            )}
            {membersOpen && (
                <ManageMembersDialog
                    channel={membersOpen}
                    users={users}
                    onClose={() => setMembersOpen(null)}
                    onUpdated={(c) => {
                        setChannels((prev) => prev.map((x) => (x.id === c.id ? c : x)));
                    }}
                />
            )}
        </section>
    );
}

function AdminCreateChannel({ onClose, onCreated }) {
    const [form, setForm] = useState({ name: "", description: "", is_private: false });
    const [error, setError] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const submit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        try {
            const { data } = await api.post("/channels", form);
            onCreated(data);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSubmitting(false);
        }
    };
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
            <form onSubmit={submit} onClick={(e) => e.stopPropagation()} className="bg-white border border-ink w-full max-w-md">
                <div className="p-4 border-b border-border">
                    <div className="ticker-label text-signal">// NEW CHANNEL</div>
                    <div className="font-heading font-extrabold text-xl tracking-tight">Create channel</div>
                </div>
                <div className="p-5 space-y-4">
                    <Input label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required testid="admin-channel-name" />
                    <Input label="Description" value={form.description} onChange={(v) => setForm({ ...form, description: v })} testid="admin-channel-desc" />
                    <label className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            checked={form.is_private}
                            onChange={(e) => setForm({ ...form, is_private: e.target.checked })}
                            data-testid="admin-channel-private"
                        />
                        <span className="text-sm">Private (invite-only)</span>
                    </label>
                    {error && <div className="border border-destructive text-destructive px-3 py-2 text-xs">{error}</div>}
                </div>
                <div className="p-4 border-t border-border flex justify-end gap-2">
                    <button type="button" className="btn-ghost" onClick={onClose}>
                        Cancel
                    </button>
                    <button type="submit" disabled={submitting} className="btn-signal" data-testid="admin-submit-channel">
                        {submitting ? "Creating…" : "Create"}
                    </button>
                </div>
            </form>
        </div>
    );
}

function ManageMembersDialog({ channel, users, onClose, onUpdated }) {
    const [current, setCurrent] = useState(channel);
    const memberSet = new Set(current.members || []);
    const available = users.filter((u) => !memberSet.has(u.id) && u.active);
    const members = users.filter((u) => memberSet.has(u.id));

    const add = async (userId) => {
        const { data } = await api.post(`/channels/${current.id}/members`, { user_ids: [userId] });
        setCurrent(data);
        onUpdated(data);
    };
    const remove = async (userId) => {
        const { data } = await api.delete(`/channels/${current.id}/members/${userId}`);
        setCurrent(data);
        onUpdated(data);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
            <div className="bg-white border border-ink w-full max-w-2xl max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()} data-testid="manage-members-dialog">
                <div className="p-4 border-b border-border">
                    <div className="ticker-label text-signal">// MEMBERS · #{current.name}</div>
                    <div className="font-heading font-extrabold text-xl tracking-tight">Manage members</div>
                </div>
                <div className="grid grid-cols-2 gap-px bg-border flex-1 min-h-0">
                    <div className="bg-white flex flex-col min-h-0">
                        <div className="ticker-label p-3 border-b border-border">In channel ({members.length})</div>
                        <div className="overflow-y-auto flex-1">
                            {members.map((u) => (
                                <div key={u.id} className="flex items-center justify-between p-3 border-b border-border">
                                    <div className="min-w-0">
                                        <div className="text-sm font-bold truncate">{u.name}</div>
                                        <div className="text-xs text-muted-foreground truncate">{u.email}</div>
                                    </div>
                                    <button className="btn-ghost text-xs px-2 py-1" onClick={() => remove(u.id)} data-testid={`remove-member-${u.email}`}>
                                        Remove
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="bg-white flex flex-col min-h-0">
                        <div className="ticker-label p-3 border-b border-border">Available ({available.length})</div>
                        <div className="overflow-y-auto flex-1">
                            {available.map((u) => (
                                <div key={u.id} className="flex items-center justify-between p-3 border-b border-border">
                                    <div className="min-w-0">
                                        <div className="text-sm font-bold truncate">{u.name}</div>
                                        <div className="text-xs text-muted-foreground truncate">{u.email}</div>
                                    </div>
                                    <button className="btn-signal text-xs px-3 py-1" onClick={() => add(u.id)} data-testid={`add-member-${u.email}`}>
                                        Add
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
                <div className="p-3 border-t border-border flex justify-end">
                    <button className="btn-ghost" onClick={onClose}>
                        Done
                    </button>
                </div>
            </div>
        </div>
    );
}

// ----- Moderation -----
function ModerationTab() {
    const [messages, setMessages] = useState([]);
    const [channels, setChannels] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [search, setSearch] = useState("");
    const [hiddenOnly, setHiddenOnly] = useState(false);
    const [channelId, setChannelId] = useState("");

    const load = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (hiddenOnly) params.set("hidden_only", "true");
            if (search) params.set("search", search);
            if (channelId) params.set("channel_id", channelId);
            const [m, c] = await Promise.all([
                api.get(`/messages/moderation/all?${params.toString()}`),
                channels.length ? Promise.resolve({ data: channels }) : api.get("/channels"),
            ]);
            setMessages(m.data);
            setChannels(c.data);
        } catch (e) {
            setError(getErrorMessage(e));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [hiddenOnly, channelId]);

    useEffect(() => {
        const t = setTimeout(() => load(), 400);
        return () => clearTimeout(t);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [search]);

    const hide = async (m) => {
        try {
            const { data } = await api.post(`/messages/${m.id}/hide`);
            setMessages((prev) => prev.map((x) => (x.id === m.id ? data : x)));
        } catch (e) {
            alert(getErrorMessage(e));
        }
    };
    const unhide = async (m) => {
        try {
            const { data } = await api.post(`/messages/${m.id}/unhide`);
            setMessages((prev) => prev.map((x) => (x.id === m.id ? data : x)));
        } catch (e) {
            alert(getErrorMessage(e));
        }
    };
    const del = async (m) => {
        if (!window.confirm("Delete this message permanently?")) return;
        try {
            await api.delete(`/messages/${m.id}`);
            setMessages((prev) => prev.filter((x) => x.id !== m.id));
        } catch (e) {
            alert(getErrorMessage(e));
        }
    };

    const channelMap = Object.fromEntries(channels.map((c) => [c.id, c]));

    return (
        <section data-testid="moderation-tab">
            <div className="mb-6">
                <h2 className="font-heading font-extrabold text-3xl tracking-tight">Moderation</h2>
                <p className="text-muted-foreground text-sm">Inspect every message, hide inappropriate content, or delete it.</p>
            </div>
            <div className="flex flex-wrap items-center gap-3 mb-4">
                <input
                    placeholder="Search text…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="border border-border focus:border-ink px-3 py-2 text-sm outline-none w-64"
                    data-testid="moderation-search"
                />
                <select
                    value={channelId}
                    onChange={(e) => setChannelId(e.target.value)}
                    className="border border-border px-3 py-2 text-sm bg-white"
                    data-testid="moderation-channel-filter"
                >
                    <option value="">All channels</option>
                    {channels.map((c) => (
                        <option key={c.id} value={c.id}>
                            #{c.name}
                        </option>
                    ))}
                </select>
                <label className="flex items-center gap-2 text-sm">
                    <input
                        type="checkbox"
                        checked={hiddenOnly}
                        onChange={(e) => setHiddenOnly(e.target.checked)}
                        data-testid="moderation-hidden-only"
                    />
                    Hidden only
                </label>
            </div>
            {error && <div className="text-destructive text-sm mb-4">{error}</div>}
            <div className="border border-border overflow-x-auto">
                <table className="w-full border-collapse text-sm" data-testid="moderation-table">
                    <thead className="bg-sidebar">
                        <tr>
                            {["Channel", "Author", "Message", "Status", "Posted", ""].map((h) => (
                                <th key={h} className="text-left ticker-label text-muted-foreground p-4 border-b border-border">
                                    {h}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan={6} className="p-6 text-center text-muted-foreground">
                                    Loading…
                                </td>
                            </tr>
                        ) : messages.length === 0 ? (
                            <tr>
                                <td colSpan={6} className="p-6 text-center text-muted-foreground">
                                    No messages match.
                                </td>
                            </tr>
                        ) : (
                            messages.map((m) => (
                                <tr
                                    key={m.id}
                                    className="border-b border-border hover:bg-surface"
                                    data-testid={`moderation-row-${m.id}`}
                                >
                                    <td className="p-4 font-bold">#{channelMap[m.channel_id]?.name || "?"}</td>
                                    <td className="p-4 text-muted-foreground">{m.user_name}</td>
                                    <td className="p-4 max-w-md">
                                        <div className="line-clamp-3 whitespace-pre-wrap break-words">
                                            {m.content || <span className="text-muted-foreground italic">(no text)</span>}
                                        </div>
                                        {m.attachments?.length > 0 && (
                                            <div className="mt-1 text-xs text-muted-foreground">
                                                {m.attachments.length} attachment(s)
                                            </div>
                                        )}
                                    </td>
                                    <td className="p-4">
                                        <span className={`ticker-label ${m.hidden ? "text-destructive" : "text-green-700"}`}>
                                            {m.hidden ? "hidden" : "visible"}
                                        </span>
                                    </td>
                                    <td className="p-4 text-xs text-muted-foreground">
                                        {new Date(m.created_at).toLocaleString()}
                                    </td>
                                    <td className="p-4">
                                        <div className="flex items-center gap-2 justify-end">
                                            {m.hidden ? (
                                                <button
                                                    className="btn-ghost text-xs px-2 py-1"
                                                    onClick={() => unhide(m)}
                                                    data-testid={`moderation-unhide-${m.id}`}
                                                >
                                                    <Eye className="w-3 h-3 inline mr-1" /> Unhide
                                                </button>
                                            ) : (
                                                <button
                                                    className="btn-ghost text-xs px-2 py-1"
                                                    onClick={() => hide(m)}
                                                    data-testid={`moderation-hide-${m.id}`}
                                                >
                                                    <EyeOff className="w-3 h-3 inline mr-1" /> Hide
                                                </button>
                                            )}
                                            <button
                                                className="btn-ghost text-xs px-2 py-1 hover:border-destructive hover:text-destructive"
                                                onClick={() => del(m)}
                                                data-testid={`moderation-delete-${m.id}`}
                                            >
                                                <Trash2 className="w-3 h-3" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </section>
    );
}
