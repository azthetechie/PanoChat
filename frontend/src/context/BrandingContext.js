import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../lib/api";

const DEFAULT_BRANDING = {
    brand_name: "PANORAMA / COMMS",
    tagline: "Internal comms · v1.0",
    hero_heading: "Built for business, shipped to your server.",
    hero_subheading:
        "Self-hosted, secure chat built for operations. Channels, media, GIFs & admin control — no third-party host.",
    logo_url: null,
    hero_image_url: null,
};

const BrandingContext = createContext({ branding: DEFAULT_BRANDING, refresh: () => {} });

export function BrandingProvider({ children }) {
    const [branding, setBranding] = useState(DEFAULT_BRANDING);

    const refresh = useCallback(async () => {
        try {
            const { data } = await api.get("/branding");
            setBranding({ ...DEFAULT_BRANDING, ...data });
        } catch {
            /* silently fall back to defaults */
        }
    }, []);

    useEffect(() => {
        refresh();
    }, [refresh]);

    return (
        <BrandingContext.Provider value={{ branding, setBranding, refresh }}>
            {children}
        </BrandingContext.Provider>
    );
}

export function useBranding() {
    return useContext(BrandingContext);
}

export function resolveAssetUrl(url) {
    if (!url) return null;
    if (url.startsWith("/")) return `${process.env.REACT_APP_BACKEND_URL}${url}`;
    return url;
}
