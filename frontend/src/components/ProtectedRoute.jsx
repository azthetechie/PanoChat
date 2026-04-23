import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children, adminOnly = false }) {
    const { user } = useAuth();
    if (user === null) {
        return (
            <div className="min-h-screen flex items-center justify-center" data-testid="auth-loading">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-ink border-t-signal animate-spin" />
                    <div className="ticker-label">Authenticating</div>
                </div>
            </div>
        );
    }
    if (user === false) return <Navigate to="/login" replace />;
    if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;
    return children;
}
