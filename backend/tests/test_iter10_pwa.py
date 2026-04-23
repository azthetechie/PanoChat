"""Iteration 10 — PWA manifest + static icons tests."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback from frontend/.env in this workspace
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN_EMAIL = "operations@panoramacoaches.com.au"
ADMIN_PASSWORD = "Pano3666"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


# ---- /api/manifest.webmanifest -------------------------------------------------
class TestManifest:
    def test_manifest_status_and_json(self):
        r = requests.get(f"{BASE_URL}/api/manifest.webmanifest", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Required PWA fields
        for key in ("name", "short_name", "start_url", "display", "theme_color", "icons"):
            assert key in data, f"missing key: {key}"
        assert data["start_url"] == "/"
        assert data["display"] == "standalone"
        assert data["theme_color"] == "#FF5A00"
        assert isinstance(data["icons"], list) and len(data["icons"]) >= 2
        sizes = {i.get("sizes") for i in data["icons"]}
        assert "192x192" in sizes
        assert "512x512" in sizes
        # at least one maskable
        purposes = {i.get("purpose") for i in data["icons"]}
        assert "maskable" in purposes

    def test_manifest_reflects_branding(self, admin_session):
        # Read current branding
        r = admin_session.get(f"{BASE_URL}/api/branding", timeout=15)
        assert r.status_code == 200, r.text
        brand_name = r.json().get("brand_name") or "Panorama Comms"

        m = requests.get(f"{BASE_URL}/api/manifest.webmanifest", timeout=15).json()
        assert m["name"] == brand_name
        # short_name derivation rule: split on "/", trim, <=12 chars
        expected_short = brand_name.split("/")[0].strip() or brand_name
        if len(expected_short) > 12:
            expected_short = expected_short[:12]
        assert m["short_name"] == expected_short


# ---- Static icons (served by frontend ingress root) ----------------------------
class TestIcons:
    @pytest.mark.parametrize("path", ["/icon-192.png", "/icon-512.png", "/icon-512-maskable.png"])
    def test_icon_served(self, path):
        r = requests.get(f"{BASE_URL}{path}", timeout=15, allow_redirects=True)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        ctype = r.headers.get("content-type", "")
        assert "image/png" in ctype, f"{path} content-type={ctype}"
        assert len(r.content) > 0


# ---- index.html wiring ---------------------------------------------------------
class TestIndexHtml:
    def test_index_html_has_pwa_tags(self):
        r = requests.get(f"{BASE_URL}/", timeout=15)
        assert r.status_code == 200
        html = r.text.lower()
        assert 'rel="manifest"' in html and "/api/manifest.webmanifest" in html
        assert 'rel="apple-touch-icon"' in html
        assert 'name="theme-color"' in html and "#ff5a00" in html
