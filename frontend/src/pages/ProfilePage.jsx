import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, getErrorMessage } from "../lib/api";
import { ArrowLeft, Check, User as UserIcon, Lock, MailCheck, Bell } from "lucide-react";
import {
    notificationsEnabled,
    requestNotificationPermission,
    setNotificationPreference,
    showDesktopNotification,
} from "../lib/notifications";

export default function ProfilePage() {
    const { user, refreshMe, setUser } = useAuth();
    const navigate = useNavigate();

    if (!user) return null;

    return (
        <div className="min-h-screen bg-white" data-testid="profile-page">
            <header className="border-b border-ink">
                <div className="flex items-center justify-between px-4 md:px-10 py-4 md:py-5">
                    <div className="flex items-center gap-3 md:gap-4 min-w-0">
                        <button
                            className="p-2 border border-border hover:border-ink shrink-0"
                            onClick={() => navigate("/")}
                            data-testid="back-to-chat-button"
                        >
                            <ArrowLeft className="w-4 h-4" />
                        </button>
                        <div className="min-w-0">
                            <div className="ticker-label text-signal">// YOUR ACCOUNT</div>
                            <div className="font-heading font-extrabold text-xl md:text-2xl tracking-tight truncate">
                                Profile & security
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            <main className="px-4 md:px-10 py-6 md:py-8 max-w-3xl mx-auto space-y-8 md:space-y-10">
                <AccountInfo
                    user={user}
                    onSaved={(u) => {
                        setUser(u);
                        refreshMe();
                    }}
                />
                <PasswordChange />
                <NotificationsSection />
                <PasswordResetRequest email={user.email} />
            </main>
        </div>
    );
}

function Section({ title, kicker, icon, children }) {
    const Icon = icon;
    return (
        <section className="border border-border">
            <header className="flex items-center gap-3 px-5 py-4 border-b border-border bg-surface">
                <div className="w-8 h-8 bg-ink flex items-center justify-center">
                    {Icon && <Icon className="w-4 h-4 text-white" />}
                </div>
                <div>
                    <div className="ticker-label text-signal">{kicker}</div>
                    <div className="font-heading font-extrabold text-xl tracking-tight">{title}</div>
                </div>
            </header>
            <div className="p-5">{children}</div>
        </section>
    );
}

function NotificationsSection() {
    const [enabled, setEnabled] = useState(notificationsEnabled());
    const [perm, setPerm] = useState(
        typeof Notification !== "undefined" ? Notification.permission : "default"
    );

    useEffect(() => {
        setEnabled(notificationsEnabled());
    }, [perm]);

    const onToggle = async () => {
        if (typeof Notification === "undefined") return;
        if (!enabled) {
            const res = await requestNotificationPermission();
            setPerm(res);
            if (res === "granted") {
                setNotificationPreference(true);
                setEnabled(true);
                showDesktopNotification("Notifications enabled", "We'll ping you for DMs & mentions.");
            }
        } else {
            setNotificationPreference(false);
            setEnabled(false);
        }
    };

    const unsupported = typeof Notification === "undefined";

    return (
        <Section title="Desktop notifications" kicker="// PING ME" icon={Bell}>
            <div className="flex items-start justify-between gap-4">
                <p className="text-sm text-muted-foreground max-w-xl">
                    Get a browser notification for new <span className="font-bold">DMs</span> and{" "}
                    <span className="font-bold">@mentions</span> when this tab is not focused.
                    No notification for regular channel chatter — only what matters.
                </p>
                <button
                    onClick={onToggle}
                    disabled={unsupported || perm === "denied"}
                    className={enabled ? "btn-signal" : "btn-ghost"}
                    data-testid="toggle-notifications-button"
                >
                    {unsupported
                        ? "Unsupported"
                        : perm === "denied"
                          ? "Blocked in browser"
                          : enabled
                            ? "Enabled"
                            : "Enable"}
                </button>
            </div>
        </Section>
    );
}


function AccountInfo({ user, onSaved }) {
    const [name, setName] = useState(user.name);
    const [avatarUrl, setAvatarUrl] = useState(user.avatar_url || "");
    const [submitting, setSubmitting] = useState(false);
    const [msg, setMsg] = useState("");
    const [error, setError] = useState("");

    const save = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        setMsg("");
        setError("");
        try {
            const { data } = await api.put("/auth/me", {
                name: name.trim(),
                avatar_url: avatarUrl.trim() || null,
            });
            onSaved?.(data);
            setMsg("Saved.");
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Section title="Display name & avatar" kicker="// IDENTITY" icon={UserIcon}>
            <form onSubmit={save} className="space-y-4" data-testid="profile-identity-form">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Field label="Full name" required>
                        <input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            required
                            data-testid="profile-name-input"
                            className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                        />
                    </Field>
                    <Field label="Email (read-only)">
                        <input
                            value={user.email}
                            disabled
                            className="w-full border border-border px-3 py-2 text-sm bg-surface text-muted-foreground"
                            data-testid="profile-email-display"
                        />
                    </Field>
                </div>
                <Field label="Avatar URL (optional)">
                    <input
                        value={avatarUrl}
                        onChange={(e) => setAvatarUrl(e.target.value)}
                        placeholder="https://… or /api/uploads/file/…"
                        className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                        data-testid="profile-avatar-input"
                    />
                </Field>
                <div className="flex items-center justify-between">
                    <div className="text-xs">
                        {msg && <span className="text-green-700">{msg}</span>}
                        {error && <span className="text-destructive">{error}</span>}
                    </div>
                    <button
                        type="submit"
                        disabled={submitting}
                        className="btn-signal flex items-center gap-2"
                        data-testid="profile-save-button"
                    >
                        <Check className="w-4 h-4" />
                        {submitting ? "Saving…" : "Save changes"}
                    </button>
                </div>
            </form>
        </Section>
    );
}

function PasswordChange() {
    const [current, setCurrent] = useState("");
    const [next, setNext] = useState("");
    const [confirm, setConfirm] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [msg, setMsg] = useState("");
    const [error, setError] = useState("");

    const submit = async (e) => {
        e.preventDefault();
        setMsg("");
        setError("");
        if (next.length < 6) return setError("New password must be at least 6 characters.");
        if (next !== confirm) return setError("Passwords do not match.");
        setSubmitting(true);
        try {
            await api.post("/auth/change-password", {
                current_password: current,
                new_password: next,
            });
            setMsg("Password updated.");
            setCurrent("");
            setNext("");
            setConfirm("");
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Section title="Change password" kicker="// SECURITY" icon={Lock}>
            <form onSubmit={submit} className="space-y-4 max-w-md" data-testid="change-password-form">
                <Field label="Current password">
                    <input
                        type="password"
                        value={current}
                        onChange={(e) => setCurrent(e.target.value)}
                        required
                        autoComplete="current-password"
                        className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                        data-testid="current-password-input"
                    />
                </Field>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Field label="New password">
                        <input
                            type="password"
                            value={next}
                            onChange={(e) => setNext(e.target.value)}
                            required
                            minLength={6}
                            autoComplete="new-password"
                            className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                            data-testid="new-password-input"
                        />
                    </Field>
                    <Field label="Confirm new password">
                        <input
                            type="password"
                            value={confirm}
                            onChange={(e) => setConfirm(e.target.value)}
                            required
                            minLength={6}
                            autoComplete="new-password"
                            className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                            data-testid="confirm-password-input"
                        />
                    </Field>
                </div>
                <div className="flex items-center justify-between">
                    <div className="text-xs">
                        {msg && <span className="text-green-700">{msg}</span>}
                        {error && <span className="text-destructive">{error}</span>}
                    </div>
                    <button
                        type="submit"
                        disabled={submitting}
                        className="btn-signal"
                        data-testid="change-password-button"
                    >
                        {submitting ? "Updating…" : "Update password"}
                    </button>
                </div>
            </form>
        </Section>
    );
}

function PasswordResetRequest({ email }) {
    const [submitting, setSubmitting] = useState(false);
    const [msg, setMsg] = useState("");
    const [error, setError] = useState("");

    const trigger = async () => {
        setSubmitting(true);
        setMsg("");
        setError("");
        try {
            await api.post("/auth/forgot-password", { email });
            setMsg(
                "A password-reset link has been generated. On a self-hosted install it is printed to the backend console; wire up email to deliver it automatically."
            );
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Section title="Password reset" kicker="// RECOVERY" icon={MailCheck}>
            <p className="text-sm text-muted-foreground max-w-xl mb-4">
                If you forget your password, a one-time reset link can be generated for your email.
                Click the button below to generate one now for <span className="font-bold">{email}</span>.
            </p>
            <div className="flex items-center justify-between">
                <div className="text-xs max-w-lg">
                    {msg && <span className="text-green-700">{msg}</span>}
                    {error && <span className="text-destructive">{error}</span>}
                </div>
                <button
                    onClick={trigger}
                    disabled={submitting}
                    className="btn-ghost"
                    data-testid="request-reset-link-button"
                >
                    {submitting ? "Generating…" : "Generate reset link"}
                </button>
            </div>
        </Section>
    );
}

function Field({ label, children }) {
    return (
        <div>
            <label className="ticker-label block mb-1">{label}</label>
            {children}
        </div>
    );
}
