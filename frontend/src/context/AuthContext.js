import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getErrorMessage } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    // null = unknown/loading; object = authenticated; false = not authenticated
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(() => localStorage.getItem("access_token"));

    const refreshMe = useCallback(async () => {
        try {
            const headers = token ? { Authorization: `Bearer ${token}` } : {};
            const { data } = await api.get("/auth/me", { headers });
            setUser(data);
            return data;
        } catch (e) {
            setUser(false);
            return null;
        }
    }, [token]);

    useEffect(() => {
        refreshMe();
    }, [refreshMe]);

    const login = useCallback(async (email, password) => {
        try {
            const { data } = await api.post("/auth/login", { email, password });
            setUser(data.user);
            if (data.access_token) {
                localStorage.setItem("access_token", data.access_token);
                setToken(data.access_token);
            }
            return { ok: true, user: data.user };
        } catch (e) {
            return { ok: false, error: getErrorMessage(e) };
        }
    }, []);

    const logout = useCallback(async () => {
        try {
            await api.post("/auth/logout");
        } catch (e) {
            /* ignore */
        }
        localStorage.removeItem("access_token");
        setToken(null);
        setUser(false);
    }, []);

    const value = { user, token, login, logout, refreshMe, setUser };
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within AuthProvider");
    return ctx;
}
