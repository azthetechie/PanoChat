import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, getErrorMessage } from "../lib/api";

export default function ResetPasswordPage() {
    const [params] = useSearchParams();
    const navigate = useNavigate();
    const tokenFromQuery = params.get("token") || "";
    const [token, setToken] = useState(tokenFromQuery);
    const [newPassword, setNewPassword] = useState("");
    const [confirm, setConfirm] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [done, setDone] = useState(false);

    // Forgot-password form (when no token present)
    const [email, setEmail] = useState("");
    const [forgotMsg, setForgotMsg] = useState("");
    const [forgotErr, setForgotErr] = useState("");

    const hasToken = useMemo(() => !!token.trim(), [token]);

    useEffect(() => {
        setToken(tokenFromQuery);
    }, [tokenFromQuery]);

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        if (newPassword.length < 6) return setError("Password must be at least 6 characters.");
        if (newPassword !== confirm) return setError("Passwords do not match.");
        setSubmitting(true);
        try {
            await api.post("/auth/reset-password", {
                token: token.trim(),
                new_password: newPassword,
            });
            setDone(true);
            setTimeout(() => navigate("/login"), 2000);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSubmitting(false);
        }
    };

    const requestLink = async (e) => {
        e.preventDefault();
        setForgotMsg("");
        setForgotErr("");
        try {
            await api.post("/auth/forgot-password", { email: email.trim().toLowerCase() });
            setForgotMsg(
                "If that email exists in our system, a reset link has been generated. Check your inbox or ask your admin (self-hosted installs print it to the backend log)."
            );
        } catch (err) {
            setForgotErr(getErrorMessage(err));
        }
    };

    return (
        <div className="min-h-screen grid place-items-center p-6" data-testid="reset-password-page">
            <div className="w-full max-w-md border border-ink bg-white">
                <div className="p-6 border-b border-border">
                    <div className="ticker-label text-signal">// RECOVERY</div>
                    <div className="font-heading font-extrabold text-2xl tracking-tight">
                        {hasToken ? "Set a new password" : "Forgot your password?"}
                    </div>
                </div>
                <div className="p-6">
                    {done ? (
                        <div
                            className="text-sm text-green-700 border border-green-700 px-3 py-2"
                            data-testid="reset-success-msg"
                        >
                            Password updated. Redirecting you to sign in…
                        </div>
                    ) : hasToken ? (
                        <form onSubmit={submit} className="space-y-4" data-testid="reset-form">
                            <div>
                                <label className="ticker-label block mb-1">Reset token</label>
                                <input
                                    value={token}
                                    onChange={(e) => setToken(e.target.value)}
                                    className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-xs font-mono"
                                    required
                                    data-testid="reset-token-input"
                                />
                            </div>
                            <div>
                                <label className="ticker-label block mb-1">New password</label>
                                <input
                                    type="password"
                                    value={newPassword}
                                    onChange={(e) => setNewPassword(e.target.value)}
                                    className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                                    required
                                    minLength={6}
                                    data-testid="reset-new-password-input"
                                />
                            </div>
                            <div>
                                <label className="ticker-label block mb-1">Confirm password</label>
                                <input
                                    type="password"
                                    value={confirm}
                                    onChange={(e) => setConfirm(e.target.value)}
                                    className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                                    required
                                    minLength={6}
                                    data-testid="reset-confirm-password-input"
                                />
                            </div>
                            {error && (
                                <div className="border border-destructive text-destructive px-3 py-2 text-xs" data-testid="reset-error">
                                    {error}
                                </div>
                            )}
                            <button
                                type="submit"
                                disabled={submitting}
                                className="btn-signal w-full"
                                data-testid="reset-submit-button"
                            >
                                {submitting ? "Updating…" : "Set new password"}
                            </button>
                        </form>
                    ) : (
                        <form onSubmit={requestLink} className="space-y-4" data-testid="forgot-form">
                            <p className="text-sm text-muted-foreground">
                                Enter your email to generate a password reset link. A link will be
                                printed to the backend log (self-hosted installs can wire up email
                                delivery).
                            </p>
                            <div>
                                <label className="ticker-label block mb-1">Email</label>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="w-full border border-border focus:border-ink outline-none px-3 py-2 text-sm"
                                    required
                                    data-testid="forgot-email-input"
                                />
                            </div>
                            {forgotMsg && (
                                <div className="text-xs text-green-700" data-testid="forgot-success-msg">{forgotMsg}</div>
                            )}
                            {forgotErr && (
                                <div className="text-xs text-destructive">{forgotErr}</div>
                            )}
                            <button type="submit" className="btn-signal w-full" data-testid="forgot-submit-button">
                                Generate reset link
                            </button>
                        </form>
                    )}
                    <div className="mt-6 text-xs text-muted-foreground">
                        <Link to="/login" className="underline decoration-signal underline-offset-2" data-testid="back-to-login-link">
                            ← Back to sign in
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    );
}
