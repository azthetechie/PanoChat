"""Shared fixtures for backend tests."""
import os
import sys
from pathlib import Path
import requests
import pytest

# Public preview URL is used because that's what the user sees and what
# CORS / cookies are configured for. WebSocket tests use localhost.
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://admin-chat-control.preview.emergentagent.com").rstrip("/")
LOCAL_URL = "http://localhost:8001"

ADMIN_EMAIL = "operations@panoramacoaches.com.au"
ADMIN_PASSWORD = "Pano3666"


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def local_url():
    return LOCAL_URL


@pytest.fixture(scope="session")
def admin_session():
    """Return a requests.Session pre-authenticated as admin (cookies + bearer)."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    data = r.json()
    token = data.get("access_token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    s.admin_user = data.get("user")
    s.access_token = token
    return s


@pytest.fixture
def fresh_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s
