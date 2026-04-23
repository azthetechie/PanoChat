import React, { useEffect, useState } from "react";
import { Download, X } from "lucide-react";

const DISMISSED_KEY = "panorama_install_dismissed_until";

function isStandalone() {
    if (typeof window === "undefined") return false;
    if (window.matchMedia?.("(display-mode: standalone)").matches) return true;
    // iOS Safari
    return !!window.navigator.standalone;
}

function isDismissedNow() {
    try {
        const raw = localStorage.getItem(DISMISSED_KEY);
        if (!raw) return false;
        const until = parseInt(raw, 10);
        return !!until && until > Date.now();
    } catch {
        return false;
    }
}

function dismissFor(days) {
    try {
        localStorage.setItem(
            DISMISSED_KEY,
            String(Date.now() + days * 24 * 60 * 60 * 1000)
        );
    } catch {
        /* ignore */
    }
}

export default function InstallAppButton() {
    const [deferredPrompt, setDeferredPrompt] = useState(null);
    const [installed, setInstalled] = useState(isStandalone());
    const [dismissed, setDismissed] = useState(isDismissedNow());

    useEffect(() => {
        const onBIP = (e) => {
            e.preventDefault();
            setDeferredPrompt(e);
        };
        const onInstalled = () => {
            setInstalled(true);
            setDeferredPrompt(null);
        };
        window.addEventListener("beforeinstallprompt", onBIP);
        window.addEventListener("appinstalled", onInstalled);
        return () => {
            window.removeEventListener("beforeinstallprompt", onBIP);
            window.removeEventListener("appinstalled", onInstalled);
        };
    }, []);

    if (installed || dismissed || !deferredPrompt) return null;

    const onInstall = async () => {
        try {
            deferredPrompt.prompt();
            const choice = await deferredPrompt.userChoice;
            if (choice.outcome === "dismissed") {
                dismissFor(7);
                setDismissed(true);
            }
        } catch {
            /* ignore */
        } finally {
            setDeferredPrompt(null);
        }
    };

    const onLater = () => {
        dismissFor(7);
        setDismissed(true);
    };

    return (
        <div
            className="flex items-center gap-1 border border-signal bg-signal text-white hover:bg-white hover:text-signal transition-colors"
            data-testid="install-app-wrap"
        >
            <button
                onClick={onInstall}
                className="flex items-center gap-2 px-3 py-1.5 text-xs font-heading font-extrabold tracking-wide uppercase"
                data-testid="install-app-button"
                title="Install Panorama Comms as an app"
            >
                <Download className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Install app</span>
                <span className="sm:hidden">Install</span>
            </button>
            <button
                onClick={onLater}
                className="px-2 py-1.5 border-l border-signal hover:bg-black/10"
                data-testid="install-app-dismiss"
                title="Not now"
                aria-label="Dismiss install prompt"
            >
                <X className="w-3 h-3" />
            </button>
        </div>
    );
}
