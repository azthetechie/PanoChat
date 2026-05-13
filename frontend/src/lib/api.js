import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
    baseURL: API_BASE,
    withCredentials: true,
});

// Always attach the Bearer token from localStorage when present.
// This makes auth survive deployments where 3rd-party cookies are blocked
// (cross-origin, Safari ITP, plain-HTTP self-host, etc.).
api.interceptors.request.use((config) => {
    try {
        const token =
            typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
        if (token) {
            config.headers = config.headers || {};
            if (!config.headers.Authorization) {
                config.headers.Authorization = `Bearer ${token}`;
            }
        }
    } catch {
        /* ignore */
    }
    return config;
});

// On 401 anywhere, drop the stale token so the app can re-auth cleanly.
api.interceptors.response.use(
    (r) => r,
    (err) => {
        if (err?.response?.status === 401) {
            try {
                if (typeof window !== "undefined") {
                    localStorage.removeItem("access_token");
                }
            } catch {
                /* ignore */
            }
        }
        return Promise.reject(err);
    }
);

export function formatApiErrorDetail(detail) {
    if (detail == null) return "Something went wrong. Please try again.";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail))
        return detail
            .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
            .filter(Boolean)
            .join(" ");
    if (detail && typeof detail.msg === "string") return detail.msg;
    return String(detail);
}

export function getErrorMessage(err) {
    return formatApiErrorDetail(err?.response?.data?.detail) || err?.message || "Request failed";
}

export function wsUrl(token) {
    const base = BACKEND_URL.replace(/^http/, "ws");
    return `${base}/api/ws${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}
