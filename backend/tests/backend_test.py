"""End-to-end backend tests for Panorama Comms.

Covers: auth, users, channels, messages/moderation, uploads, giphy,
brute-force lockout, and WebSocket flow (against localhost).
"""
import asyncio
import io
import json
import os
import time
import uuid
import pytest
import requests
import websockets

from conftest import BASE_URL, LOCAL_URL, ADMIN_EMAIL, ADMIN_PASSWORD


# ---------- Health ----------

class TestHealth:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_root(self):
        r = requests.get(f"{BASE_URL}/api/", timeout=10)
        assert r.status_code == 200
        assert r.json().get("service") == "panorama-comms"


# ---------- Auth ----------

class TestAuth:
    def test_login_admin_success_sets_cookies_and_returns_token(self, fresh_session):
        r = fresh_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "access_token" in body and isinstance(body["access_token"], str)
        assert body["user"]["email"] == ADMIN_EMAIL
        assert body["user"]["role"] == "admin"
        assert "password_hash" not in body["user"]
        # cookies
        ck_names = {c.name for c in fresh_session.cookies}
        assert "access_token" in ck_names and "refresh_token" in ck_names

    def test_login_invalid_password(self, fresh_session):
        r = fresh_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": "wrongwrong"},
            timeout=15,
        )
        assert r.status_code == 401

    def test_me_with_bearer(self, admin_session):
        # Bearer-only path
        s = requests.Session()
        s.headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {admin_session.access_token}",
            }
        )
        r = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_me_with_cookie_only(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        login = s.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert login.status_code == 200
        # Strip Authorization, rely on cookie
        r = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_refresh_with_cookie(self):
        s = requests.Session()
        s.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        r = s.post(f"{BASE_URL}/api/auth/refresh", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_refresh_without_cookie_unauthorized(self):
        r = requests.post(f"{BASE_URL}/api/auth/refresh", timeout=10)
        assert r.status_code == 401

    def test_logout_clears_cookies(self):
        s = requests.Session()
        s.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        r = s.post(f"{BASE_URL}/api/auth/logout", timeout=15)
        assert r.status_code == 200
        # After logout the cookie is cleared so /me should be 401
        r2 = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r2.status_code == 401

    def test_change_password_then_revert(self, admin_session):
        # change to a new password, login with it, then change back to original.
        new_pw = "Pano3666_temp"
        r = admin_session.post(
            f"{BASE_URL}/api/auth/change-password",
            json={"current_password": ADMIN_PASSWORD, "new_password": new_pw},
            timeout=15,
        )
        assert r.status_code == 200, r.text

        # verify new password works
        s2 = requests.Session()
        ok = s2.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": new_pw},
            timeout=15,
        )
        assert ok.status_code == 200

        # restore original
        bad = admin_session.post(
            f"{BASE_URL}/api/auth/change-password",
            json={"current_password": new_pw, "new_password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert bad.status_code == 200


# ---------- Users (admin) ----------

@pytest.fixture(scope="module")
def created_user(admin_session):
    """Create a test user once for the module and cleanup after."""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = admin_session.post(
        f"{BASE_URL}/api/users",
        json={"email": email, "password": "Passw0rd!", "name": "TEST User", "role": "user"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    user = r.json()
    user["password"] = "Passw0rd!"
    yield user
    # cleanup
    admin_session.delete(f"{BASE_URL}/api/users/{user['id']}", timeout=15)


class TestUsers:
    def test_list_users_authenticated(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/users", timeout=15)
        assert r.status_code == 200
        users = r.json()
        assert any(u["email"] == ADMIN_EMAIL for u in users)
        # password_hash should not leak
        assert all("password_hash" not in u for u in users)

    def test_list_users_unauth_blocked(self):
        r = requests.get(f"{BASE_URL}/api/users", timeout=10)
        assert r.status_code == 401

    def test_create_user_persists(self, admin_session, created_user):
        # GET it back
        all_users = admin_session.get(f"{BASE_URL}/api/users", timeout=15).json()
        assert any(u["id"] == created_user["id"] for u in all_users)

    def test_non_admin_cannot_create_user(self, created_user):
        s = requests.Session()
        login = s.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": created_user["email"], "password": created_user["password"]},
            timeout=15,
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        s.headers.update({"Authorization": f"Bearer {token}"})
        r = s.post(
            f"{BASE_URL}/api/users",
            json={"email": "x@y.com", "password": "x" * 8, "name": "Nope"},
            timeout=15,
        )
        assert r.status_code == 403

    def test_patch_user_role_and_active(self, admin_session, created_user):
        r = admin_session.patch(
            f"{BASE_URL}/api/users/{created_user['id']}",
            json={"role": "admin", "active": True},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["role"] == "admin"
        # revert
        admin_session.patch(
            f"{BASE_URL}/api/users/{created_user['id']}",
            json={"role": "user"},
            timeout=15,
        )

    def test_admin_cannot_demote_self(self, admin_session):
        r = admin_session.patch(
            f"{BASE_URL}/api/users/{admin_session.admin_user['id']}",
            json={"role": "user"},
            timeout=15,
        )
        assert r.status_code == 400

    def test_admin_cannot_deactivate_self(self, admin_session):
        r = admin_session.patch(
            f"{BASE_URL}/api/users/{admin_session.admin_user['id']}",
            json={"active": False},
            timeout=15,
        )
        assert r.status_code == 400

    def test_admin_cannot_delete_self(self, admin_session):
        r = admin_session.delete(
            f"{BASE_URL}/api/users/{admin_session.admin_user['id']}", timeout=15
        )
        assert r.status_code == 400


# ---------- Channels ----------

@pytest.fixture(scope="module")
def public_channel(admin_session):
    name = f"test-pub-{uuid.uuid4().hex[:6]}"
    r = admin_session.post(
        f"{BASE_URL}/api/channels",
        json={"name": name, "description": "TEST public", "is_private": False},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    ch = r.json()
    yield ch
    admin_session.delete(f"{BASE_URL}/api/channels/{ch['id']}", timeout=15)


@pytest.fixture(scope="module")
def private_channel(admin_session):
    name = f"test-priv-{uuid.uuid4().hex[:6]}"
    r = admin_session.post(
        f"{BASE_URL}/api/channels",
        json={"name": name, "description": "TEST private", "is_private": True},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    ch = r.json()
    yield ch
    admin_session.delete(f"{BASE_URL}/api/channels/{ch['id']}", timeout=15)


class TestChannels:
    def test_list_channels(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/channels", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_public_channel_includes_all_users(self, admin_session, public_channel):
        users = admin_session.get(f"{BASE_URL}/api/users", timeout=15).json()
        active_ids = {u["id"] for u in users if u.get("active", True)}
        assert active_ids.issubset(set(public_channel["members"]))
        assert public_channel["is_private"] is False

    def test_create_private_channel_only_admin(self, admin_session, private_channel):
        assert private_channel["is_private"] is True
        assert private_channel["members"] == [admin_session.admin_user["id"]]

    def test_update_channel(self, admin_session, public_channel):
        r = admin_session.patch(
            f"{BASE_URL}/api/channels/{public_channel['id']}",
            json={"description": "Updated desc"},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["description"] == "Updated desc"

    def test_add_and_remove_members(self, admin_session, private_channel, created_user):
        r = admin_session.post(
            f"{BASE_URL}/api/channels/{private_channel['id']}/members",
            json={"user_ids": [created_user["id"]]},
            timeout=15,
        )
        assert r.status_code == 200
        assert created_user["id"] in r.json()["members"]
        # remove
        r2 = admin_session.delete(
            f"{BASE_URL}/api/channels/{private_channel['id']}/members/{created_user['id']}",
            timeout=15,
        )
        assert r2.status_code == 200
        assert created_user["id"] not in r2.json()["members"]

    def test_delete_channel_cascades_messages(self, admin_session):
        # create dedicated channel + message, then delete
        name = f"test-cascade-{uuid.uuid4().hex[:6]}"
        ch = admin_session.post(
            f"{BASE_URL}/api/channels",
            json={"name": name, "description": "x", "is_private": False},
            timeout=15,
        ).json()
        msg = admin_session.post(
            f"{BASE_URL}/api/messages/channel/{ch['id']}",
            json={"content": "to be cascaded", "attachments": []},
            timeout=15,
        ).json()
        assert "id" in msg
        # delete channel
        d = admin_session.delete(f"{BASE_URL}/api/channels/{ch['id']}", timeout=15)
        assert d.status_code == 200
        # messages list against deleted channel returns 404
        r = admin_session.get(f"{BASE_URL}/api/messages/channel/{ch['id']}", timeout=15)
        assert r.status_code == 404


# ---------- Messages ----------

class TestMessages:
    def test_post_text_message(self, admin_session, public_channel):
        r = admin_session.post(
            f"{BASE_URL}/api/messages/channel/{public_channel['id']}",
            json={"content": "Hello world", "attachments": []},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["content"] == "Hello world"
        assert m["channel_id"] == public_channel["id"]

    def test_post_empty_message_rejected(self, admin_session, public_channel):
        r = admin_session.post(
            f"{BASE_URL}/api/messages/channel/{public_channel['id']}",
            json={"content": "   ", "attachments": []},
            timeout=15,
        )
        assert r.status_code == 400

    def test_list_messages_with_pagination(self, admin_session, public_channel):
        for i in range(3):
            admin_session.post(
                f"{BASE_URL}/api/messages/channel/{public_channel['id']}",
                json={"content": f"msg-{i}", "attachments": []},
                timeout=15,
            )
        r = admin_session.get(
            f"{BASE_URL}/api/messages/channel/{public_channel['id']}?limit=2",
            timeout=15,
        )
        assert r.status_code == 200
        assert len(r.json()) <= 2

    def test_hide_unhide_masks_for_non_admin(self, admin_session, public_channel, created_user):
        # post as admin
        msg = admin_session.post(
            f"{BASE_URL}/api/messages/channel/{public_channel['id']}",
            json={"content": "secret-content", "attachments": []},
            timeout=15,
        ).json()

        # admin hides
        h = admin_session.post(f"{BASE_URL}/api/messages/{msg['id']}/hide", timeout=15)
        assert h.status_code == 200
        assert h.json()["hidden"] is True

        # non-admin should see masked content
        s = requests.Session()
        login = s.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": created_user["email"], "password": created_user["password"]},
            timeout=15,
        )
        token = login.json()["access_token"]
        s.headers.update({"Authorization": f"Bearer {token}"})
        msgs = s.get(
            f"{BASE_URL}/api/messages/channel/{public_channel['id']}", timeout=15
        ).json()
        target = next((m for m in msgs if m["id"] == msg["id"]), None)
        assert target is not None
        assert "hidden by admin" in target["content"]
        assert target["attachments"] == []

        # admin sees real content
        admin_msgs = admin_session.get(
            f"{BASE_URL}/api/messages/channel/{public_channel['id']}", timeout=15
        ).json()
        admin_target = next((m for m in admin_msgs if m["id"] == msg["id"]), None)
        assert admin_target["content"] == "secret-content"

        # unhide
        u = admin_session.post(f"{BASE_URL}/api/messages/{msg['id']}/unhide", timeout=15)
        assert u.status_code == 200
        assert u.json()["hidden"] is False

    def test_delete_message_others_forbidden(self, admin_session, public_channel, created_user):
        # admin posts a message
        msg = admin_session.post(
            f"{BASE_URL}/api/messages/channel/{public_channel['id']}",
            json={"content": "owned-by-admin", "attachments": []},
            timeout=15,
        ).json()
        # user tries to delete
        s = requests.Session()
        login = s.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": created_user["email"], "password": created_user["password"]},
            timeout=15,
        )
        token = login.json()["access_token"]
        s.headers.update({"Authorization": f"Bearer {token}"})
        r = s.delete(f"{BASE_URL}/api/messages/{msg['id']}", timeout=15)
        assert r.status_code == 403
        # admin can delete
        d = admin_session.delete(f"{BASE_URL}/api/messages/{msg['id']}", timeout=15)
        assert d.status_code == 200

    def test_moderation_endpoint(self, admin_session, public_channel):
        # post + hide one
        msg = admin_session.post(
            f"{BASE_URL}/api/messages/channel/{public_channel['id']}",
            json={"content": "needle-xyz", "attachments": []},
            timeout=15,
        ).json()
        admin_session.post(f"{BASE_URL}/api/messages/{msg['id']}/hide", timeout=15)
        r = admin_session.get(
            f"{BASE_URL}/api/messages/moderation/all?hidden_only=true&search=needle-xyz",
            timeout=15,
        )
        assert r.status_code == 200
        assert any(m["id"] == msg["id"] for m in r.json())

    def test_moderation_requires_admin(self, created_user):
        s = requests.Session()
        login = s.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": created_user["email"], "password": created_user["password"]},
            timeout=15,
        )
        token = login.json()["access_token"]
        s.headers.update({"Authorization": f"Bearer {token}"})
        r = s.get(f"{BASE_URL}/api/messages/moderation/all", timeout=15)
        assert r.status_code == 403


# ---------- Uploads ----------

# 1x1 PNG
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6300010000050001a5f6450b0000000049454e44ae426082"
)


class TestUploads:
    def test_upload_png_and_serve(self, admin_session):
        files = {"file": ("test.png", PNG_BYTES, "image/png")}
        # remove Content-Type json header so multipart works
        headers = {k: v for k, v in admin_session.headers.items() if k.lower() != "content-type"}
        r = requests.post(
            f"{BASE_URL}/api/uploads/image", files=files, headers=headers, timeout=20
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["url"].startswith("/api/uploads/file/")
        # GET the file
        served = requests.get(f"{BASE_URL}{body['url']}", timeout=15)
        assert served.status_code == 200
        assert len(served.content) == len(PNG_BYTES)

    def test_upload_rejects_exe(self, admin_session):
        files = {"file": ("evil.exe", b"MZ\x90\x00", "application/octet-stream")}
        headers = {k: v for k, v in admin_session.headers.items() if k.lower() != "content-type"}
        r = requests.post(
            f"{BASE_URL}/api/uploads/image", files=files, headers=headers, timeout=15
        )
        assert r.status_code == 400


# ---------- Giphy ----------

class TestGiphy:
    def test_giphy_search(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/giphy/search?q=cat&limit=3", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "results" in body
        assert isinstance(body["results"], list)
        assert len(body["results"]) >= 1

    def test_giphy_trending(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/giphy/trending?limit=3", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "results" in body and isinstance(body["results"], list)
        assert len(body["results"]) >= 1


# ---------- Brute-force lockout ----------

class TestBruteForce:
    def test_brute_force_lock_after_5_failures_localhost(self):
        """Run against localhost: the public ingress load-balances across
        multiple upstream pods (different request.client.host per request),
        so per-IP brute-force tracking can't trigger via the public URL.
        See action_items in the test report."""
        email = f"brute_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        saw_429 = False
        for i in range(7):
            r = s.post(
                f"{LOCAL_URL}/api/auth/login",
                json={"email": email, "password": "WRONG"},
                timeout=10,
            )
            if r.status_code == 429:
                saw_429 = True
                break
        assert saw_429, "Expected 429 lockout after 5 failed attempts (localhost)"


# ---------- WebSocket (against localhost; ingress may not pass WS) ----------

class TestWebSocket:
    def _login_local(self):
        r = requests.post(
            f"{LOCAL_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200
        return r.json()["access_token"]

    def test_ws_unauthenticated_rejected(self):
        async def run():
            uri = "ws://localhost:8001/api/ws"
            try:
                async with websockets.connect(uri) as ws:
                    # Should be closed immediately
                    await asyncio.wait_for(ws.recv(), timeout=2)
                    return False
            except Exception:
                return True
        ok = asyncio.run(run())
        assert ok, "Expected WS to be closed/refused without token"

    def test_ws_subscribe_and_broadcast_on_post(self, admin_session, public_channel):
        token = self._login_local()
        chan_id = public_channel["id"]

        async def run():
            uri = f"ws://localhost:8001/api/ws?token={token}"
            async with websockets.connect(uri) as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                assert hello.get("type") == "hello"
                await ws.send(json.dumps({"type": "subscribe", "channel_id": chan_id}))
                ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                assert ack.get("type") == "subscribed"

                # Trigger a message via REST and wait for broadcast
                def post_msg():
                    requests.post(
                        f"{LOCAL_URL}/api/messages/channel/{chan_id}",
                        json={"content": "ws-broadcast-test", "attachments": []},
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {token}",
                        },
                        timeout=10,
                    )
                loop = asyncio.get_running_loop()
                loop.call_later(0.3, post_msg)

                got_event = False
                deadline = time.time() + 5
                while time.time() < deadline:
                    try:
                        evt = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                    except asyncio.TimeoutError:
                        break
                    if evt.get("type") == "message:new" and evt["message"]["content"] == "ws-broadcast-test":
                        got_event = True
                        break
                return got_event

        assert asyncio.run(run()), "Did not receive message:new broadcast"
