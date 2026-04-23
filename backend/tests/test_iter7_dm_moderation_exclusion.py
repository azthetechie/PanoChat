"""Iter-7 targeted tests: DMs must be excluded from admin Moderation endpoint.

Fix under test:
    GET /api/messages/moderation/all (admin-only) must never surface messages
    whose channel has type='dm'. Even a direct channel_id filter pointed at a
    DM channel must return []. Non-DM (public/private) channel filtering must
    continue to work.
"""
import uuid
import pytest
import requests

from conftest import BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD


# ---------- Helpers ----------
def _login(email, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"], r.json()["user"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_ctx():
    tok, user = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return {"token": tok, "user": user, "headers": _hdr(tok)}


@pytest.fixture(scope="module")
def ephemeral_user(admin_ctx):
    suffix = uuid.uuid4().hex[:6]
    email = f"iter7dmmod_{suffix}@example.com"
    password = "TestPass123!"
    r = requests.post(
        f"{BASE_URL}/api/users",
        headers=admin_ctx["headers"],
        json={
            "email": email,
            "name": f"Iter7 DM User {suffix}",
            "password": password,
            "role": "user",
        },
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    uid = r.json()["id"]
    tok, user = _login(email, password)
    yield {"id": uid, "token": tok, "user": user, "email": email, "headers": _hdr(tok)}
    try:
        requests.delete(
            f"{BASE_URL}/api/users/{uid}", headers=admin_ctx["headers"], timeout=10
        )
    except Exception:
        pass


@pytest.fixture(scope="module")
def seeded(admin_ctx, ephemeral_user):
    """Create:
       - one DM channel (admin<->ephemeral) with a uniquely-marked DM message
       - post a uniquely-marked public-channel message to the first non-DM channel
       Track message IDs so we can delete them on teardown.
    """
    marker = uuid.uuid4().hex[:8]
    dm_text = f"TEST_ITER7_DM_{marker} pizza"
    pub_text = f"TEST_ITER7_PUB_{marker} pizza"

    # 1) Open DM as ephemeral user (admin sits on the other side)
    r = requests.post(
        f"{BASE_URL}/api/dms",
        headers=ephemeral_user["headers"],
        json={"user_id": admin_ctx["user"]["id"]},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    dm_channel_id = r.json()["id"]

    # 2) Post DM message from ephemeral user
    r = requests.post(
        f"{BASE_URL}/api/messages/channel/{dm_channel_id}",
        headers=ephemeral_user["headers"],
        json={"content": dm_text, "attachments": [], "mentions": []},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    dm_msg_id = r.json()["id"]

    # 3) Find a non-DM channel the admin can post to
    r = requests.get(f"{BASE_URL}/api/channels", headers=admin_ctx["headers"], timeout=15)
    assert r.status_code == 200, r.text
    channels = r.json()
    # channels endpoint already excludes DMs (per review note); but be defensive
    non_dm = [c for c in channels if c.get("type") != "dm"]
    assert non_dm, "Expected at least one non-DM channel to exist for regression baseline"
    pub_channel_id = non_dm[0]["id"]

    # 4) Post a public-channel message as admin
    r = requests.post(
        f"{BASE_URL}/api/messages/channel/{pub_channel_id}",
        headers=admin_ctx["headers"],
        json={"content": pub_text, "attachments": [], "mentions": []},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    pub_msg_id = r.json()["id"]

    yield {
        "marker": marker,
        "dm_channel_id": dm_channel_id,
        "dm_msg_id": dm_msg_id,
        "dm_text": dm_text,
        "pub_channel_id": pub_channel_id,
        "pub_msg_id": pub_msg_id,
        "pub_text": pub_text,
    }

    # teardown — delete both messages (admin can delete any)
    for mid in (dm_msg_id, pub_msg_id):
        try:
            requests.delete(
                f"{BASE_URL}/api/messages/{mid}",
                headers=admin_ctx["headers"],
                timeout=10,
            )
        except Exception:
            pass


# ---------- Tests ----------
class TestDmExcludedFromModeration:
    def test_moderation_unfiltered_has_no_dm_messages(self, admin_ctx, seeded):
        """GET /api/messages/moderation/all with no filter must NOT contain
        any DM messages, but should still surface the public one."""
        r = requests.get(
            f"{BASE_URL}/api/messages/moderation/all?limit=1000",
            headers=admin_ctx["headers"],
            timeout=20,
        )
        assert r.status_code == 200, r.text
        docs = r.json()
        assert isinstance(docs, list)
        ids = {d["id"] for d in docs}
        # DM msg must NOT be present
        assert seeded["dm_msg_id"] not in ids, (
            f"DM message leaked into moderation list: {seeded['dm_msg_id']}"
        )
        # The DM channel_id must not appear at all
        dm_channel_leaks = [d for d in docs if d["channel_id"] == seeded["dm_channel_id"]]
        assert not dm_channel_leaks, f"Moderation list contained DM-channel msgs: {dm_channel_leaks}"
        # Public message should appear (regression guard)
        assert seeded["pub_msg_id"] in ids, "Public-channel msg missing from moderation list"

    def test_moderation_search_returns_no_dm_matches(self, admin_ctx, seeded):
        """Both DM and public messages contain 'pizza' + marker. Search must
        return only the public one."""
        term = f"TEST_ITER7_"  # matches both our seeded messages; marker makes it unique
        r = requests.get(
            f"{BASE_URL}/api/messages/moderation/all",
            headers=admin_ctx["headers"],
            params={"search": seeded["marker"], "limit": 200},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        docs = r.json()
        ids = {d["id"] for d in docs}
        assert seeded["dm_msg_id"] not in ids, "DM matched via search — must be excluded"
        assert seeded["pub_msg_id"] in ids, "Public msg should match via search"
        # Every returned doc must NOT be from the DM channel
        for d in docs:
            assert d["channel_id"] != seeded["dm_channel_id"]
        # Sanity: at least our public match came back
        assert any(seeded["marker"] in d.get("content", "") for d in docs)
        # silence unused-var
        _ = term

    def test_moderation_channel_id_filter_on_dm_returns_empty(self, admin_ctx, seeded):
        """Admin cannot override the DM exclusion by passing channel_id=<DM_ID>."""
        r = requests.get(
            f"{BASE_URL}/api/messages/moderation/all",
            headers=admin_ctx["headers"],
            params={"channel_id": seeded["dm_channel_id"], "limit": 200},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        docs = r.json()
        assert docs == [], f"Expected [] for DM channel filter, got {len(docs)} docs"

    def test_moderation_channel_id_filter_on_public_still_works(self, admin_ctx, seeded):
        """Regression: filtering by a public channel still returns only that channel's messages."""
        r = requests.get(
            f"{BASE_URL}/api/messages/moderation/all",
            headers=admin_ctx["headers"],
            params={"channel_id": seeded["pub_channel_id"], "limit": 200},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        docs = r.json()
        assert isinstance(docs, list) and len(docs) >= 1
        for d in docs:
            assert d["channel_id"] == seeded["pub_channel_id"], (
                f"Filter leaked other channel msg: {d['channel_id']}"
            )
        ids = {d["id"] for d in docs}
        assert seeded["pub_msg_id"] in ids

    def test_dm_channel_messages_endpoint_still_works_for_participants(
        self, ephemeral_user, seeded
    ):
        """Regression: /api/messages/channel/{dm_id} still returns DMs to participants."""
        r = requests.get(
            f"{BASE_URL}/api/messages/channel/{seeded['dm_channel_id']}",
            headers=ephemeral_user["headers"],
            timeout=15,
        )
        assert r.status_code == 200, r.text
        docs = r.json()
        ids = {d["id"] for d in docs}
        assert seeded["dm_msg_id"] in ids

    def test_dms_list_still_shows_dm(self, ephemeral_user, seeded):
        """Regression: GET /api/dms still surfaces the DM to its participant."""
        r = requests.get(
            f"{BASE_URL}/api/dms", headers=ephemeral_user["headers"], timeout=15
        )
        assert r.status_code == 200, r.text
        dm_ids = {d["id"] for d in r.json()}
        assert seeded["dm_channel_id"] in dm_ids
