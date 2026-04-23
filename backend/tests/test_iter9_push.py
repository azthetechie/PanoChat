"""Iteration 9: Web-Push notification endpoint tests.

Coverage:
- GET /api/push/vapid-public-key (unauthenticated) — returns base64url EC P-256 pubkey (~87 chars, starts with 'B')
- POST /api/push/subscribe (auth) — upserts subscription, validates payload
- POST /api/push/unsubscribe (auth) — deletes subscription
- POST /api/push/test (auth) — no-op safe, doesn't 500
- VAPID key persistence — same key returned before/after we re-request
- Messaging: posting a message in a public channel triggers _fire_push safely (no 500)
"""
import os
import re
import requests
import pytest

BASE = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://admin-chat-control.preview.emergentagent.com",
).rstrip("/")


# ---------- VAPID public key ----------

class TestVapidPublicKey:
    def test_unauthenticated_get_returns_valid_key(self):
        r = requests.get(f"{BASE}/api/push/vapid-public-key", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "public_key" in data
        pk = data["public_key"]
        assert isinstance(pk, str)
        # base64url: A-Z a-z 0-9 - _ ; no padding
        assert re.fullmatch(r"[A-Za-z0-9_-]+", pk), f"Not base64url: {pk!r}"
        # Uncompressed EC P-256 point = 65 raw bytes => ceil(65*4/3) = 87 chars base64url no padding
        assert 85 <= len(pk) <= 90, f"Unexpected length {len(pk)}: {pk}"
        assert pk.startswith("B"), f"Uncompressed EC point should start with 'B' (0x04): {pk[:4]}"

    def test_vapid_key_is_stable(self):
        """Calling twice returns the same key (persistence in DB)."""
        r1 = requests.get(f"{BASE}/api/push/vapid-public-key", timeout=15).json()["public_key"]
        r2 = requests.get(f"{BASE}/api/push/vapid-public-key", timeout=15).json()["public_key"]
        assert r1 == r2


# ---------- Subscribe / Unsubscribe ----------

# A fake but well-formed subscription (endpoint + P-256 pubkey + auth secret).
# The endpoint is not a real push service — pywebpush send will fail gracefully
# during /push/test, which is the intended path (we only assert no 500 from our API).
FAKE_SUB = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/TEST_ITER9_FAKE_ENDPOINT_PANORAMA",
    "keys": {
        # 65-byte EC P-256 uncompressed public key, base64url
        "p256dh": "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U",
        # 16-byte auth secret, base64url
        "auth": "tBHItJI5svbpez7KI4CCXg",
    },
    "expirationTime": None,
}


class TestPushSubscribe:
    def test_subscribe_requires_auth(self):
        r = requests.post(f"{BASE}/api/push/subscribe", json=FAKE_SUB, timeout=15)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}: {r.text}"

    def test_subscribe_rejects_invalid_payload(self, admin_session):
        r = admin_session.post(f"{BASE}/api/push/subscribe", json={"endpoint": "https://x"}, timeout=15)
        # Missing keys -> pydantic 422
        assert r.status_code in (400, 422), f"Got {r.status_code}: {r.text}"

    def test_subscribe_rejects_empty_endpoint(self, admin_session):
        bad = {"endpoint": "", "keys": {"p256dh": "x", "auth": "y"}}
        r = admin_session.post(f"{BASE}/api/push/subscribe", json=bad, timeout=15)
        assert r.status_code in (400, 422)

    def test_subscribe_ok_upserts(self, admin_session):
        r = admin_session.post(f"{BASE}/api/push/subscribe", json=FAKE_SUB, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}

        # Idempotent upsert: calling again must still return ok
        r2 = admin_session.post(f"{BASE}/api/push/subscribe", json=FAKE_SUB, timeout=15)
        assert r2.status_code == 200

    def test_unsubscribe_requires_auth(self):
        r = requests.post(
            f"{BASE}/api/push/unsubscribe", json={"endpoint": FAKE_SUB["endpoint"]}, timeout=15
        )
        assert r.status_code in (401, 403)

    def test_unsubscribe_ok(self, admin_session):
        # Ensure subscribed first
        admin_session.post(f"{BASE}/api/push/subscribe", json=FAKE_SUB, timeout=15)
        r = admin_session.post(
            f"{BASE}/api/push/unsubscribe", json={"endpoint": FAKE_SUB["endpoint"]}, timeout=15
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}

        # Double unsubscribe is safe (no-op)
        r2 = admin_session.post(
            f"{BASE}/api/push/unsubscribe", json={"endpoint": FAKE_SUB["endpoint"]}, timeout=15
        )
        assert r2.status_code == 200


# ---------- Test push endpoint ----------

class TestPushTestEndpoint:
    def test_requires_auth(self):
        r = requests.post(f"{BASE}/api/push/test", timeout=15)
        assert r.status_code in (401, 403)

    def test_no_subs_returns_ok(self, admin_session):
        # Ensure no sub exists for admin
        admin_session.post(
            f"{BASE}/api/push/unsubscribe", json={"endpoint": FAKE_SUB["endpoint"]}, timeout=15
        )
        r = admin_session.post(f"{BASE}/api/push/test", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}

    def test_with_fake_sub_does_not_500(self, admin_session):
        """With a fake (unreachable) subscription registered, /push/test must not raise 500.
        pywebpush will fail to deliver but our handler should swallow the error."""
        admin_session.post(f"{BASE}/api/push/subscribe", json=FAKE_SUB, timeout=15)
        try:
            r = admin_session.post(f"{BASE}/api/push/test", timeout=30)
            assert r.status_code == 200, r.text
        finally:
            admin_session.post(
                f"{BASE}/api/push/unsubscribe",
                json={"endpoint": FAKE_SUB["endpoint"]},
                timeout=15,
            )


# ---------- _fire_push is non-breaking ----------

class TestMessageSendFirePushSafe:
    def test_send_message_in_public_channel_does_not_500_with_fake_sub(self, admin_session):
        """Ensure posting a message works even if a fake push sub exists.
        This exercises routes/messages._fire_push against a fake endpoint for offline users
        (if any). Admin is online so their own subs are skipped, but we still verify the
        endpoint chain completes with 200."""
        # Find any public (non-dm) channel
        r = admin_session.get(f"{BASE}/api/channels", timeout=15)
        assert r.status_code == 200
        chans = [c for c in r.json() if c.get("type") != "dm"]
        assert chans, "No public channels available"
        ch_id = chans[0]["id"]

        # Register a fake sub (for admin — will be skipped since admin is online/sender)
        admin_session.post(f"{BASE}/api/push/subscribe", json=FAKE_SUB, timeout=15)

        try:
            r = admin_session.post(
                f"{BASE}/api/messages/channel/{ch_id}",
                json={"content": "TEST_iter9 push _fire_push safety probe"},
                timeout=20,
            )
            assert r.status_code in (200, 201), f"Got {r.status_code}: {r.text}"
            msg = r.json()
            assert msg.get("id")
            # Cleanup message
            admin_session.delete(f"{BASE}/api/messages/{msg['id']}", timeout=15)
        finally:
            admin_session.post(
                f"{BASE}/api/push/unsubscribe",
                json={"endpoint": FAKE_SUB["endpoint"]},
                timeout=15,
            )


# ---------- Service worker file ----------

class TestServiceWorkerServed:
    def test_sw_js_reachable(self):
        r = requests.get(f"{BASE}/sw.js", timeout=15)
        assert r.status_code == 200, f"sw.js not reachable: {r.status_code}"
        ct = r.headers.get("content-type", "")
        # CRA may serve as application/javascript or text/javascript
        assert "javascript" in ct.lower(), f"Unexpected content-type: {ct}"
        body = r.text
        assert "push" in body and "notificationclick" in body
