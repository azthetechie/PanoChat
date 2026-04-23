"""Tests for iteration-3 unread tracking endpoints:
- GET  /api/channels/unread
- POST /api/channels/{id}/read
"""
import os
import time
import uuid
import requests
import pytest

from conftest import BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD


@pytest.fixture(scope="module")
def user_b(admin_session):
    """Create a second ephemeral user and return a dict with an authed session."""
    email = f"unread_b_{uuid.uuid4().hex[:6]}@example.com"
    password = "UnreadB123!"
    r = admin_session.post(
        f"{BASE_URL}/api/users",
        json={"email": email, "password": password, "name": "Unread B", "role": "user"},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    uid = r.json()["id"]

    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    login = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    assert login.status_code == 200, login.text
    s.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})

    yield {"id": uid, "email": email, "password": password, "session": s}

    admin_session.delete(f"{BASE_URL}/api/users/{uid}", timeout=15)


@pytest.fixture(scope="module")
def public_channel_unread(admin_session):
    name = f"unread-pub-{uuid.uuid4().hex[:6]}"
    r = admin_session.post(
        f"{BASE_URL}/api/channels",
        json={"name": name, "description": "TEST unread public", "is_private": False},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    ch = r.json()
    yield ch
    admin_session.delete(f"{BASE_URL}/api/channels/{ch['id']}", timeout=15)


@pytest.fixture(scope="module")
def private_channel_admin_only(admin_session):
    """Private channel that user_b is NOT a member of."""
    name = f"unread-priv-{uuid.uuid4().hex[:6]}"
    r = admin_session.post(
        f"{BASE_URL}/api/channels",
        json={"name": name, "description": "TEST unread priv", "is_private": True},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    ch = r.json()
    yield ch
    admin_session.delete(f"{BASE_URL}/api/channels/{ch['id']}", timeout=15)


class TestUnreadBackend:
    def test_unread_returns_dict_of_accessible_channels(self, admin_session, public_channel_unread):
        r = admin_session.get(f"{BASE_URL}/api/channels/unread", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)
        # every value must be int
        for k, v in data.items():
            assert isinstance(v, int)
        # the public test channel must appear (admin has access)
        assert public_channel_unread["id"] in data

    def test_unread_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/channels/unread", timeout=15)
        assert r.status_code == 401

    def test_other_user_post_increments_unread_for_admin(
        self, admin_session, user_b, public_channel_unread
    ):
        cid = public_channel_unread["id"]
        # Admin marks channel as read first to baseline
        r0 = admin_session.post(f"{BASE_URL}/api/channels/{cid}/read", timeout=15)
        assert r0.status_code == 200
        time.sleep(1.0)  # ensure created_at > last_read_at (iso seconds resolution)

        baseline = admin_session.get(f"{BASE_URL}/api/channels/unread", timeout=15).json()
        assert baseline.get(cid, 0) == 0, f"expected 0 after mark-read, got {baseline.get(cid)}"

        # User B posts a message
        post = user_b["session"].post(
            f"{BASE_URL}/api/messages/channel/{cid}",
            json={"content": "hello from B", "attachments": []},
            timeout=15,
        )
        assert post.status_code == 200, post.text

        # Admin unread should be +1
        after = admin_session.get(f"{BASE_URL}/api/channels/unread", timeout=15).json()
        assert after.get(cid, 0) == 1, f"expected 1, got {after.get(cid)}"

    def test_own_message_does_not_increment_own_unread(
        self, admin_session, public_channel_unread
    ):
        cid = public_channel_unread["id"]
        # mark read
        admin_session.post(f"{BASE_URL}/api/channels/{cid}/read", timeout=15)
        time.sleep(1.0)
        # admin posts their own message
        r = admin_session.post(
            f"{BASE_URL}/api/messages/channel/{cid}",
            json={"content": "own msg admin", "attachments": []},
            timeout=15,
        )
        assert r.status_code == 200
        # admin unread for this channel stays at 0
        counts = admin_session.get(f"{BASE_URL}/api/channels/unread", timeout=15).json()
        assert counts.get(cid, 0) == 0

    def test_hidden_message_does_not_count_as_unread(
        self, admin_session, user_b, public_channel_unread
    ):
        cid = public_channel_unread["id"]
        # User B marks read
        user_b["session"].post(f"{BASE_URL}/api/channels/{cid}/read", timeout=15)
        time.sleep(1.0)

        # Admin posts; then hides it
        msg = admin_session.post(
            f"{BASE_URL}/api/messages/channel/{cid}",
            json={"content": "will-be-hidden", "attachments": []},
            timeout=15,
        ).json()
        h = admin_session.post(f"{BASE_URL}/api/messages/{msg['id']}/hide", timeout=15)
        assert h.status_code == 200

        # B's unread for this channel should be 0 (hidden excluded)
        b_counts = user_b["session"].get(f"{BASE_URL}/api/channels/unread", timeout=15).json()
        assert b_counts.get(cid, 0) == 0, f"hidden message should not count, got {b_counts.get(cid)}"

        # cleanup: unhide
        admin_session.post(f"{BASE_URL}/api/messages/{msg['id']}/unhide", timeout=15)

    def test_post_read_resets_unread_to_zero(
        self, admin_session, user_b, public_channel_unread
    ):
        cid = public_channel_unread["id"]
        # Ensure some unread first
        admin_session.post(f"{BASE_URL}/api/channels/{cid}/read", timeout=15)
        time.sleep(1.0)
        user_b["session"].post(
            f"{BASE_URL}/api/messages/channel/{cid}",
            json={"content": "build up unread", "attachments": []},
            timeout=15,
        )
        counts_before = admin_session.get(f"{BASE_URL}/api/channels/unread", timeout=15).json()
        assert counts_before.get(cid, 0) >= 1

        # POST /read clears it
        r = admin_session.post(f"{BASE_URL}/api/channels/{cid}/read", timeout=15)
        assert r.status_code == 200
        assert "last_read_at" in r.json()
        time.sleep(0.2)
        counts_after = admin_session.get(f"{BASE_URL}/api/channels/unread", timeout=15).json()
        assert counts_after.get(cid, 0) == 0

    def test_private_channel_not_visible_to_non_member(
        self, user_b, private_channel_admin_only
    ):
        cid = private_channel_admin_only["id"]
        r = user_b["session"].get(f"{BASE_URL}/api/channels/unread", timeout=15)
        assert r.status_code == 200
        assert cid not in r.json(), "non-member should not see private channel in unread map"

    def test_mark_read_on_private_denied_for_non_member(
        self, user_b, private_channel_admin_only
    ):
        cid = private_channel_admin_only["id"]
        r = user_b["session"].post(f"{BASE_URL}/api/channels/{cid}/read", timeout=15)
        assert r.status_code == 403

    def test_mark_read_on_unknown_channel_404(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/channels/does-not-exist-{uuid.uuid4().hex[:6]}/read",
            timeout=15,
        )
        assert r.status_code == 404
