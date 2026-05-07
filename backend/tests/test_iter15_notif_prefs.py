"""Iter15: notification prefs (server-side quiet hours that gate push)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import requests

BASE = "http://localhost:8001"


@pytest.fixture
def admin_session():
    s = requests.Session()
    r = s.post(
        f"{BASE}/api/auth/login",
        json={"email": "operations@panoramacoaches.com.au", "password": "Pano3666"},
        timeout=15,
    )
    r.raise_for_status()
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


def _reset(s):
    s.put(
        f"{BASE}/api/me/notifications",
        json={
            "quiet_hours": {"enabled": False, "start": "22:00", "end": "07:00", "timezone": "UTC"},
            "mute_until": None,
            "push_enabled": True,
        },
        timeout=15,
    )


class TestEndpoints:
    def test_get_defaults(self, admin_session):
        _reset(admin_session)
        r = admin_session.get(f"{BASE}/api/me/notifications", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["quiet_hours"]["enabled"] is False
        assert body["push_enabled"] is True

    def test_put_persists(self, admin_session):
        body = {
            "quiet_hours": {
                "enabled": True,
                "start": "21:00",
                "end": "08:00",
                "timezone": "Australia/Sydney",
            },
            "mute_until": None,
            "push_enabled": True,
        }
        r = admin_session.put(f"{BASE}/api/me/notifications", json=body, timeout=15)
        assert r.status_code == 200, r.text
        r2 = admin_session.get(f"{BASE}/api/me/notifications", timeout=15)
        assert r2.json()["quiet_hours"]["enabled"] is True
        assert r2.json()["quiet_hours"]["timezone"] == "Australia/Sydney"
        _reset(admin_session)

    def test_invalid_time_format(self, admin_session):
        body = {
            "quiet_hours": {
                "enabled": True,
                "start": "bad",
                "end": "07:00",
                "timezone": "UTC",
            },
            "mute_until": None,
            "push_enabled": True,
        }
        r = admin_session.put(f"{BASE}/api/me/notifications", json=body, timeout=15)
        assert r.status_code == 422

    def test_requires_auth(self):
        r = requests.get(f"{BASE}/api/me/notifications", timeout=15)
        assert r.status_code in (401, 403)


class TestQuietHoursHelper:
    """Direct unit tests on the helper used by _fire_push."""

    def test_overnight_window(self):
        from routes.notification_prefs import in_quiet_hours_for_user

        u = {
            "notification_prefs": {
                "quiet_hours": {
                    "enabled": True,
                    "start": "22:00",
                    "end": "07:00",
                    "timezone": "Australia/Sydney",
                }
            }
        }
        # 03:00 Sydney → in quiet
        t = datetime(2026, 5, 7, 3, 0, tzinfo=ZoneInfo("Australia/Sydney"))
        assert in_quiet_hours_for_user(u, t) is True
        # 12:00 Sydney → not in quiet
        t = datetime(2026, 5, 7, 12, 0, tzinfo=ZoneInfo("Australia/Sydney"))
        assert in_quiet_hours_for_user(u, t) is False

    def test_disabled_returns_false(self):
        from routes.notification_prefs import in_quiet_hours_for_user

        u = {"notification_prefs": {"quiet_hours": {"enabled": False}}}
        assert in_quiet_hours_for_user(u) is False

    def test_legacy_user_no_prefs(self):
        from routes.notification_prefs import push_allowed_for_user

        assert push_allowed_for_user({}) is True

    def test_push_disabled_blocks(self):
        from routes.notification_prefs import push_allowed_for_user

        u = {"notification_prefs": {"push_enabled": False}}
        assert push_allowed_for_user(u) is False
