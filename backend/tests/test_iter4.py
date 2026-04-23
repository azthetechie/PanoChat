"""Iteration-4 backend tests: DMs, mentions, reactions."""
import uuid
import pytest
import requests

from conftest import BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD


# ---------- Helpers ----------

def _make_user(admin_session, prefix="iter4"):
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
    u = _make_user(admin_session, "iter4a")
    yield u
    admin_session.delete(f"{BASE_URL}/api/users/{u['id']}", timeout=15)


@pytest.fixture(scope="module")
def user_b(admin_session):
    u = _make_user(admin_session, "iter4b")
    yield u
    admin_session.delete(f"{BASE_URL}/api/users/{u['id']}", timeout=15)


@pytest.fixture(scope="module")
def session_a(user_a):
    return _login(user_a["email"], user_a["password"])


@pytest.fixture(scope="module")
def session_b(user_b):
    return _login(user_b["email"], user_b["password"])


# ---------- DM creation ----------

class TestDMCreate:
    def test_create_dm_returns_dm_payload(self, session_a, user_b):
        r = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15)
        assert r.status_code == 200, r.text
        dm = r.json()
        assert dm["other_user_id"] == user_b["id"]
        assert dm["other_user_email"] == user_b["email"]
        assert "id" in dm

    def test_create_dm_is_idempotent(self, session_a, user_b):
        r1 = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15)
        r2 = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15)
        assert r1.status_code == r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]

    def test_dm_same_id_for_either_participant(self, session_a, session_b, user_a, user_b):
        a_view = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15).json()
        b_view = session_b.post(f"{BASE_URL}/api/dms", json={"user_id": user_a["id"]}, timeout=15).json()
        assert a_view["id"] == b_view["id"]
        assert a_view["other_user_id"] == user_b["id"]
        assert b_view["other_user_id"] == user_a["id"]

    def test_cannot_dm_self(self, session_a, user_a):
        r = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_a["id"]}, timeout=15)
        assert r.status_code == 400

    def test_cannot_dm_missing_user(self, session_a):
        r = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": str(uuid.uuid4())}, timeout=15)
        assert r.status_code == 404

    def test_cannot_dm_deactivated_user(self, admin_session, session_a):
        # create + deactivate
        ephemeral = _make_user(admin_session, "iter4dead")
        admin_session.patch(
            f"{BASE_URL}/api/users/{ephemeral['id']}", json={"active": False}, timeout=15
        )
        try:
            r = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": ephemeral["id"]}, timeout=15)
            assert r.status_code == 403
        finally:
            admin_session.delete(f"{BASE_URL}/api/users/{ephemeral['id']}", timeout=15)


# ---------- DM listing ----------

class TestDMList:
    def test_list_dms_includes_created_dm(self, session_a, user_b):
        session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15)
        r = session_a.get(f"{BASE_URL}/api/dms", timeout=15)
        assert r.status_code == 200
        dms = r.json()
        assert any(d["other_user_id"] == user_b["id"] for d in dms)

    def test_list_dms_after_message_has_preview_and_unread(self, session_a, session_b, user_a, user_b):
        dm = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15).json()
        # B sends a message to A
        session_b.post(
            f"{BASE_URL}/api/messages/channel/{dm['id']}",
            json={"content": "hi from B", "attachments": []},
            timeout=15,
        )
        r = session_a.get(f"{BASE_URL}/api/dms", timeout=15)
        assert r.status_code == 200
        target = next(d for d in r.json() if d["id"] == dm["id"])
        assert target["last_message_preview"] == "hi from B"
        assert target["last_message_at"] is not None
        assert target["unread"] >= 1


# ---------- DMs excluded from /api/channels ----------

class TestDMExcludedFromChannels:
    def test_dm_not_in_channels_for_admin(self, admin_session, session_a, user_b):
        dm = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15).json()
        chans = admin_session.get(f"{BASE_URL}/api/channels", timeout=15).json()
        assert all(c["id"] != dm["id"] for c in chans)
        assert all(c.get("type", "channel") != "dm" for c in chans)

    def test_dm_not_in_channels_for_user(self, session_a, user_b):
        dm = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15).json()
        chans = session_a.get(f"{BASE_URL}/api/channels", timeout=15).json()
        assert all(c["id"] != dm["id"] for c in chans)


# ---------- DM messaging ACL ----------

class TestDMMessaging:
    def test_both_participants_can_post(self, session_a, session_b, user_a, user_b):
        dm = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15).json()
        ra = session_a.post(
            f"{BASE_URL}/api/messages/channel/{dm['id']}",
            json={"content": "from A", "attachments": []},
            timeout=15,
        )
        rb = session_b.post(
            f"{BASE_URL}/api/messages/channel/{dm['id']}",
            json={"content": "from B", "attachments": []},
            timeout=15,
        )
        assert ra.status_code == 200
        assert rb.status_code == 200

    def test_third_party_forbidden(self, admin_session, session_a, user_b):
        # third user
        c = _make_user(admin_session, "iter4c")
        try:
            sc = _login(c["email"], c["password"])
            dm = session_a.post(f"{BASE_URL}/api/dms", json={"user_id": user_b["id"]}, timeout=15).json()
            r = sc.post(
                f"{BASE_URL}/api/messages/channel/{dm['id']}",
                json={"content": "hello", "attachments": []},
                timeout=15,
            )
            assert r.status_code == 403
            r2 = sc.get(f"{BASE_URL}/api/messages/channel/{dm['id']}", timeout=15)
            assert r2.status_code == 403
        finally:
            admin_session.delete(f"{BASE_URL}/api/users/{c['id']}", timeout=15)


# ---------- Mentions ----------

class TestMentions:
    def test_post_with_mentions_persists(self, admin_session, session_a, user_b):
        # find admin user id
        admin_id = admin_session.admin_user["id"]
        # use the general public channel: create one
        name = f"mentest-{uuid.uuid4().hex[:6]}"
        ch = admin_session.post(
            f"{BASE_URL}/api/channels",
            json={"name": name, "description": "x", "is_private": False},
            timeout=15,
        ).json()
        try:
            r = session_a.post(
                f"{BASE_URL}/api/messages/channel/{ch['id']}",
                json={"content": f"hey @admin and @b", "attachments": [], "mentions": [admin_id, user_b["id"]]},
                timeout=15,
            )
            assert r.status_code == 200, r.text
            msg = r.json()
            assert "mentions" in msg
            assert set(msg["mentions"]) == {admin_id, user_b["id"]}
        finally:
            admin_session.delete(f"{BASE_URL}/api/channels/{ch['id']}", timeout=15)

    def test_self_mention_filtered(self, admin_session, session_a, user_a):
        name = f"selfmen-{uuid.uuid4().hex[:6]}"
        ch = admin_session.post(
            f"{BASE_URL}/api/channels",
            json={"name": name, "description": "x", "is_private": False},
            timeout=15,
        ).json()
        try:
            r = session_a.post(
                f"{BASE_URL}/api/messages/channel/{ch['id']}",
                json={"content": "hey me", "attachments": [], "mentions": [user_a["id"]]},
                timeout=15,
            )
            assert r.status_code == 200
            assert user_a["id"] not in r.json()["mentions"]
        finally:
            admin_session.delete(f"{BASE_URL}/api/channels/{ch['id']}", timeout=15)


# ---------- Reactions ----------

class TestReactions:
    def test_react_toggle(self, admin_session, session_a):
        name = f"reacttest-{uuid.uuid4().hex[:6]}"
        ch = admin_session.post(
            f"{BASE_URL}/api/channels",
            json={"name": name, "description": "x", "is_private": False},
            timeout=15,
        ).json()
        try:
            msg = session_a.post(
                f"{BASE_URL}/api/messages/channel/{ch['id']}",
                json={"content": "react to me", "attachments": []},
                timeout=15,
            ).json()
            # add reaction
            r1 = session_a.post(
                f"{BASE_URL}/api/messages/{msg['id']}/react",
                json={"emoji": "👍"},
                timeout=15,
            )
            assert r1.status_code == 200, r1.text
            assert "👍" in r1.json()["reactions"]
            assert session_a.user["id"] in r1.json()["reactions"]["👍"]
            # toggle off
            r2 = session_a.post(
                f"{BASE_URL}/api/messages/{msg['id']}/react",
                json={"emoji": "👍"},
                timeout=15,
            )
            assert r2.status_code == 200
            assert "👍" not in r2.json()["reactions"]
        finally:
            admin_session.delete(f"{BASE_URL}/api/channels/{ch['id']}", timeout=15)

    def test_react_non_member_private_forbidden(self, admin_session, session_a):
        # create private channel admin-only
        name = f"reactpriv-{uuid.uuid4().hex[:6]}"
        ch = admin_session.post(
            f"{BASE_URL}/api/channels",
            json={"name": name, "description": "x", "is_private": True},
            timeout=15,
        ).json()
        try:
            # admin posts message
            msg = admin_session.post(
                f"{BASE_URL}/api/messages/channel/{ch['id']}",
                json={"content": "secret", "attachments": []},
                timeout=15,
            ).json()
            # session_a (non-member) reacts -> 403
            r = session_a.post(
                f"{BASE_URL}/api/messages/{msg['id']}/react",
                json={"emoji": "🔥"},
                timeout=15,
            )
            assert r.status_code == 403
        finally:
            admin_session.delete(f"{BASE_URL}/api/channels/{ch['id']}", timeout=15)

    def test_react_message_not_found(self, session_a):
        r = session_a.post(
            f"{BASE_URL}/api/messages/{uuid.uuid4()}/react",
            json={"emoji": "👍"},
            timeout=15,
        )
        assert r.status_code == 404
