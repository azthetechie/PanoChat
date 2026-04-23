"""Iteration-5 backend tests: email fallback, DM unique index, message threads."""
import os
import uuid
import subprocess
import pytest
import requests

from conftest import BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD


# ---------- Helpers ----------

def _make_user(admin_session, prefix="iter5"):
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Passw0rd!"
    r = admin_session.post(
        f"{BASE_URL}/api/users",
        json={"email": email, "password": pw, "name": f"TEST {prefix}", "role": "user"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    u = r.json()
    u["password"] = pw
    return u


def _login(email, password):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    s.user = r.json()["user"]
    return s


@pytest.fixture(scope="module")
def user_a(admin_session):
    u = _make_user(admin_session, "iter5a")
    yield u
    admin_session.delete(f"{BASE_URL}/api/users/{u['id']}", timeout=15)


@pytest.fixture(scope="module")
def user_b(admin_session):
    u = _make_user(admin_session, "iter5b")
    yield u
    admin_session.delete(f"{BASE_URL}/api/users/{u['id']}", timeout=15)


@pytest.fixture(scope="module")
def session_a(user_a):
    return _login(user_a["email"], user_a["password"])


@pytest.fixture(scope="module")
def session_b(user_b):
    return _login(user_b["email"], user_b["password"])


@pytest.fixture(scope="module")
def public_channel(admin_session):
    name = f"iter5pub-{uuid.uuid4().hex[:6]}"
    ch = admin_session.post(
        f"{BASE_URL}/api/channels",
        json={"name": name, "description": "x", "is_private": False},
        timeout=15,
    ).json()
    yield ch
    admin_session.delete(f"{BASE_URL}/api/channels/{ch['id']}", timeout=15)


# =====================================================================
# EMAIL / forgot-password
# =====================================================================
class TestForgotPasswordEmail:
    def test_forgot_password_always_ok_for_known_user(self, fresh_session, admin_session):
        u = _make_user(admin_session, "iter5mail")
        try:
            r = fresh_session.post(
                f"{BASE_URL}/api/auth/forgot-password",
                json={"email": u["email"]},
                timeout=15,
            )
            assert r.status_code == 200, r.text
            assert r.json().get("ok") is True
        finally:
            admin_session.delete(f"{BASE_URL}/api/users/{u['id']}", timeout=15)

    def test_forgot_password_ok_for_unknown_user(self, fresh_session):
        r = fresh_session.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": f"nobody_{uuid.uuid4().hex[:6]}@example.com"},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_forgot_password_fallback_logs_link(self, fresh_session, admin_session):
        """Unverified recipient → Resend will bounce → fallback log present."""
        u = _make_user(admin_session, "iter5fallback")
        try:
            # Clear recent backend log marker by capturing time of request
            r = fresh_session.post(
                f"{BASE_URL}/api/auth/forgot-password",
                json={"email": u["email"]},
                timeout=20,
            )
            assert r.status_code == 200
            # Inspect backend log for the fallback line
            log = subprocess.run(
                ["tail", "-n", "300", "/var/log/supervisor/backend.err.log"],
                capture_output=True, text=True, timeout=5,
            ).stdout + subprocess.run(
                ["tail", "-n", "300", "/var/log/supervisor/backend.out.log"],
                capture_output=True, text=True, timeout=5,
            ).stdout
            # Either success log OR fallback log must mention this address
            assert (
                f"Password reset email sent to {u['email']}" in log
                or f"[PASSWORD_RESET] (fallback) link for {u['email']}" in log
                or f"[PASSWORD_RESET] (email disabled" in log
            ), "No email-service log line found for the test user"
        finally:
            admin_session.delete(f"{BASE_URL}/api/users/{u['id']}", timeout=15)


# =====================================================================
# DM unique index (race fix)
# =====================================================================
class TestDMUniqueIndex:
    def test_partial_unique_index_exists(self):
        """Check db.channels has partial unique index on name where type=dm."""
        from pymongo import MongoClient
        cli = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = cli[os.environ.get("DB_NAME", "test_database")]
        idx = db.channels.index_information()
        # Find any index that is unique AND has a partialFilterExpression with type=dm
        match = None
        for name, info in idx.items():
            pf = info.get("partialFilterExpression")
            if info.get("unique") and pf and pf.get("type") == "dm":
                match = (name, info)
                break
        assert match is not None, f"No partial unique DM index found. Indexes: {list(idx.keys())}"

    def test_consecutive_dm_posts_return_same_channel(self, session_a, user_b):
        r1 = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15)
        r2 = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15)
        r3 = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15)
        assert r1.status_code == r2.status_code == r3.status_code == 200
        assert r1.json()["id"] == r2.json()["id"] == r3.json()["id"]


# =====================================================================
# Threads
# =====================================================================
class TestThreads:
    def test_post_reply_increments_parent_count(self, session_a, public_channel):
        ch_id = public_channel["id"]
        parent = session_a.post(
            f"{BASE_URL}/api/messages/channel/{ch_id}",
            json={"content": "parent-msg", "attachments": []},
            timeout=15,
        ).json()
        assert parent.get("thread_reply_count", 0) == 0

        reply = session_a.post(
            f"{BASE_URL}/api/messages/channel/{ch_id}",
            json={"content": "reply-1", "attachments": [], "parent_id": parent["id"]},
            timeout=15,
        )
        assert reply.status_code == 200, reply.text
        rj = reply.json()
        assert rj["parent_id"] == parent["id"]

        # Fetch thread → parent + 1 reply; parent count=1; last_reply_at set
        t = session_a.get(f"{BASE_URL}/api/messages/{parent['id']}/thread", timeout=15).json()
        assert len(t) == 2
        assert t[0]["id"] == parent["id"]
        assert t[1]["id"] == rj["id"]
        assert t[0]["thread_reply_count"] == 1
        assert t[0]["thread_last_reply_at"] is not None

    def test_list_messages_excludes_thread_replies(self, session_a, public_channel):
        ch_id = public_channel["id"]
        parent = session_a.post(
            f"{BASE_URL}/api/messages/channel/{ch_id}",
            json={"content": "top-level-A", "attachments": []},
            timeout=15,
        ).json()
        reply = session_a.post(
            f"{BASE_URL}/api/messages/channel/{ch_id}",
            json={"content": "reply-A", "attachments": [], "parent_id": parent["id"]},
            timeout=15,
        ).json()
        msgs = session_a.get(f"{BASE_URL}/api/messages/channel/{ch_id}", timeout=15).json()
        ids = [m["id"] for m in msgs]
        assert parent["id"] in ids
        assert reply["id"] not in ids, "thread replies must not appear in the channel list"

    def test_thread_endpoint_orders_oldest_first(self, session_a, public_channel):
        ch_id = public_channel["id"]
        parent = session_a.post(
            f"{BASE_URL}/api/messages/channel/{ch_id}",
            json={"content": "order-parent", "attachments": []},
            timeout=15,
        ).json()
        r1 = session_a.post(
            f"{BASE_URL}/api/messages/channel/{ch_id}",
            json={"content": "first-reply", "attachments": [], "parent_id": parent["id"]},
            timeout=15,
        ).json()
        r2 = session_a.post(
            f"{BASE_URL}/api/messages/channel/{ch_id}",
            json={"content": "second-reply", "attachments": [], "parent_id": parent["id"]},
            timeout=15,
        ).json()
        t = session_a.get(f"{BASE_URL}/api/messages/{parent['id']}/thread", timeout=15).json()
        assert [m["id"] for m in t] == [parent["id"], r1["id"], r2["id"]]

    def test_reply_to_reply_flattens_to_root(self, session_a, public_channel):
        ch_id = public_channel["id"]
        parent = session_a.post(
            f"{BASE_URL}/api/messages/channel/{ch_id}",
            json={"content": "root", "attachments": []},
            timeout=15,
        ).json()
        r1 = session_a.post(
            f"{BASE_URL}/api/messages/channel/{ch_id}",
            json={"content": "mid", "attachments": [], "parent_id": parent["id"]},
            timeout=15,
        ).json()
        r2 = session_a.post(
            f"{BASE_URL}/api/messages/channel/{ch_id}",
            json={"content": "nested", "attachments": [], "parent_id": r1["id"]},
            timeout=15,
        )
        assert r2.status_code == 200
        assert r2.json()["parent_id"] == parent["id"], "reply-to-reply must flatten to the root parent"

    def test_unknown_parent_id_404(self, session_a, public_channel):
        ch_id = public_channel["id"]
        r = session_a.post(
            f"{BASE_URL}/api/messages/channel/{ch_id}",
            json={"content": "x", "attachments": [], "parent_id": str(uuid.uuid4())},
            timeout=15,
        )
        assert r.status_code == 404

    def test_parent_in_different_channel_404(self, session_a, admin_session, public_channel):
        other_name = f"iter5other-{uuid.uuid4().hex[:6]}"
        other = admin_session.post(
            f"{BASE_URL}/api/channels",
            json={"name": other_name, "description": "", "is_private": False},
            timeout=15,
        ).json()
        try:
            parent_in_other = session_a.post(
                f"{BASE_URL}/api/messages/channel/{other['id']}",
                json={"content": "elsewhere", "attachments": []},
                timeout=15,
            ).json()
            r = session_a.post(
                f"{BASE_URL}/api/messages/channel/{public_channel['id']}",
                json={"content": "cross", "attachments": [], "parent_id": parent_in_other["id"]},
                timeout=15,
            )
            assert r.status_code == 404
        finally:
            admin_session.delete(f"{BASE_URL}/api/channels/{other['id']}", timeout=15)

    def test_thread_unknown_message_404(self, session_a):
        r = session_a.get(f"{BASE_URL}/api/messages/{uuid.uuid4()}/thread", timeout=15)
        assert r.status_code == 404


# =====================================================================
# Regression: login still works, brute force
# =====================================================================
class TestLoginRegression:
    def test_admin_login(self, fresh_session):
        r = fresh_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200
        assert "access_token" in r.json()
