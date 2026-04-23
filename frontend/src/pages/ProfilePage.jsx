import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, getErrorMessage } from "../lib/api";
import { ArrowLeft, Check, User as UserIcon, Lock, MailCheck } from "lucide-react";

export default function ProfilePage() {
    const { user, refreshMe, setUser } = useAuth();
    const navigate = useNavigate();

    if (!user) return null;

    return (
        <div className="min-h-screen bg-white" data-testid="profile-page">
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
                            <div className="ticker-label text-signal">// YOUR ACCOUNT</div>
                            <div className="font-heading font-extrabold text-2xl tracking-tight">
                                Profile & security
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            <main className="px-6 md:px-10 py-8 max-w-3xl mx-auto space-y-10">
                <AccountInfo
                    user={user}
                    onSaved={(u) => {
                        setUser(u);
                        refreshMe();
                    }}
                />
                <PasswordChange />
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
