import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useBranding, resolveAssetUrl } from "../context/BrandingContext";
import { Lock, Mail, ArrowRight } from "lucide-react";

export default function LoginPage() {
    const { login, user } = useAuth();
    const { branding } = useBranding();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        if (user && user !== false) navigate("/", { replace: true });
    }, [user, navigate]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setSubmitting(true);
        const res = await login(email.trim().toLowerCase(), password);
        setSubmitting(false);
        if (res.ok) navigate("/", { replace: true });
        else setError(res.error || "Login failed");
    };

    const logoUrl = resolveAssetUrl(branding.logo_url);
    const heroUrl = resolveAssetUrl(branding.hero_image_url);
    const brandName = branding.brand_name || "PANORAMA / COMMS";
    const tagline = branding.tagline || "Internal comms · v1.0";
    const heroHeading = branding.hero_heading || "Built for business, shipped to your server.";
    const heroSubheading = branding.hero_subheading || "";

    return (
        <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2" data-testid="login-page">
            {/* Left: form */}
            <div className="flex flex-col justify-between p-8 md:p-12">
                <div className="flex items-center gap-3" data-testid="brand-logo">
                    {logoUrl ? (
                        <img
                            src={logoUrl}
                            alt={brandName}
                            className="h-10 w-10 object-contain border border-border bg-white"
                            data-testid="brand-logo-image"
                        />
                    ) : (
                        <div className="w-10 h-10 bg-ink flex items-center justify-center">
                            <div className="w-3 h-3 bg-signal" />
                        </div>
                    )}
                    <div>
                        <div className="font-heading font-extrabold text-lg tracking-tight leading-none" data-testid="brand-name">
                            {brandName}
                        </div>
                        <div className="ticker-label text-muted-foreground">{tagline}</div>
                    </div>
                </div>

                <div className="max-w-md w-full mx-auto lg:mx-0 py-12">
                    <div className="ticker-label text-signal mb-4">// SECURE SIGN IN</div>
                    <h1 className="font-heading font-extrabold text-4xl md:text-5xl tracking-tight leading-[0.95] mb-6">
                        Speak with your <br /> team. Everywhere.
                    </h1>
                    <p className="text-muted-foreground mb-10 max-w-sm">
                        Self-hosted, secure chat built for operations. Channels, media, GIFs &
                        admin control — no third-party host.
                    </p>

                    <form onSubmit={handleSubmit} className="space-y-5" data-testid="login-form">
                        <div>
                            <label className="ticker-label block mb-2" htmlFor="email">Email</label>
                            <div className="flex items-center border border-ink">
                                <div className="px-3 border-r border-ink"><Mail className="w-4 h-4" /></div>
                                <input
                                    id="email"
                                    data-testid="login-email-input"
                                    type="email"
                                    autoComplete="email"
                                    required
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="you@company.com"
                                    className="flex-1 px-3 py-3 bg-white outline-none placeholder:text-muted-foreground"
                                />
                            </div>
                        </div>
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <label className="ticker-label" htmlFor="password">Password</label>
                                <Link
                                    to="/forgot-password"
                                    className="ticker-label text-signal hover:underline"
                                    data-testid="forgot-password-link"
                                >
                                    Forgot?
                                </Link>
                            </div>
                            <div className="flex items-center border border-ink">
                                <div className="px-3 border-r border-ink"><Lock className="w-4 h-4" /></div>
                                <input
                                    id="password"
                                    data-testid="login-password-input"
                                    type="password"
                                    autoComplete="current-password"
                                    required
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className="flex-1 px-3 py-3 bg-white outline-none placeholder:text-muted-foreground"
                                />
                            </div>
                        </div>

                        {error && (
                            <div
                                className="border border-destructive bg-destructive/5 text-destructive px-4 py-2 text-sm"
                                data-testid="login-error"
                            >
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={submitting}
                            className="btn-signal w-full flex items-center justify-center gap-2 group"
                            data-testid="login-submit-button"
                        >
                            {submitting ? "Signing in…" : "Sign in"}
                            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                        </button>
                    </form>
                </div>

                <div className="ticker-label text-muted-foreground" data-testid="login-footer">
                    Self-hosted · No external auth · JWT + bcrypt
                </div>
            </div>

            {/* Right: high-contrast brandable panel */}
            <div
                className="hidden lg:flex flex-col bg-ink text-white relative overflow-hidden"
                data-testid="login-hero-panel"
            >
                {heroUrl && (
                    <div
                        className="absolute inset-0 bg-cover bg-center"
                        style={{ backgroundImage: `url(${heroUrl})` }}
                        data-testid="login-hero-image"
                    />
                )}
                <div className="absolute inset-0 bg-ink/80" />
                <div className="absolute inset-0 opacity-[0.08]">
                    <div className="w-full h-full hero-grid" />
                </div>
                <div className="relative z-10 p-12 flex-1 flex flex-col justify-between">
                    <div className="flex items-center justify-between">
                        <div className="ticker-label text-signal">// LIVE OPS FEED</div>
                        <div className="ticker-label text-white/60">
                            NODE / 01 · {new Date().toLocaleDateString()}
                        </div>
                    </div>

                    <div className="space-y-6">
                        <div className="h-px w-24 bg-signal" />
                        <div className="font-heading font-extrabold text-5xl tracking-tight leading-[0.95]">
                            {heroHeading}
                        </div>
                        {heroSubheading && (
                            <div className="text-white/70 max-w-xl text-lg" data-testid="login-hero-subheading">
                                {heroSubheading}
                            </div>
                        )}
                        <div className="grid grid-cols-3 gap-px bg-white/10 border border-white/10">
                            {[
                                { k: "Channels", v: "Unlimited" },
                                { k: "Media", v: "IMG · GIF" },
                                { k: "Auth", v: "JWT · bcrypt" },
                            ].map((m) => (
                                <div key={m.k} className="bg-ink p-5">
                                    <div className="ticker-label text-white/60">{m.k}</div>
                                    <div className="font-heading font-bold text-xl mt-1">{m.v}</div>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="flex items-end justify-between">
                        <div>
                            <div className="ticker-label text-white/60">Deploy target</div>
                            <div className="font-heading font-bold text-xl">Docker / Self-hosted</div>
                        </div>
                        <div className="diag-stripe w-28 h-8 opacity-80" />
                    </div>
                </div>
            </div>
        </div>
    );
}
