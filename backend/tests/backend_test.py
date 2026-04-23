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


# ---------- Brute force via PUBLIC URL (regression for X-Forwarded-For fix) ----------

class TestBruteForcePublic:
    def test_brute_force_lock_after_5_failures_via_public_url(self):
        """5 wrong logins through the public URL should result in 429 on attempt 6.
        Previously failed because per-IP counter used request.client.host (upstream
        ingress pod IP). Now should honor X-Forwarded-For/X-Real-IP."""
        email = f"bf_pub_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        statuses = []
        for i in range(7):
            r = s.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": email, "password": "WRONG"},
                timeout=15,
            )
            statuses.append(r.status_code)
            if r.status_code == 429:
                break
        assert 429 in statuses, f"Expected 429 lockout via public URL, got: {statuses}"
        # Should be locked at exactly attempt 6 (index 5)
        first_429 = statuses.index(429)
        assert first_429 == 5, f"Expected first 429 at attempt 6, got at attempt {first_429+1}: {statuses}"

    def test_brute_force_email_secondary_blocks_across_ips(self):
        """Even with different X-Forwarded-For values, the email-only secondary
        counter should still throttle distributed attacks."""
        email = f"bf_email_{uuid.uuid4().hex[:8]}@example.com"
        statuses = []
        for i in range(7):
            # Use a different fake IP each time to defeat the ip:email counter
            fake_ip = f"203.0.113.{i+1}"
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": email, "password": "WRONG"},
                headers={"X-Forwarded-For": fake_ip, "Content-Type": "application/json"},
                timeout=15,
            )
            statuses.append(r.status_code)
            if r.status_code == 429:
                break
        # NOTE: ingress will overwrite/append to X-Forwarded-For, so the *real*
        # X-Forwarded-For seen by the app may not equal fake_ip. The point of
        # this test is that the email-only counter must still trip 429 within 7 attempts.
        assert 429 in statuses, f"Email-only secondary lockout did not trigger: {statuses}"


# ---------- Profile update PUT /api/auth/me ----------

class TestProfileUpdate:
    def test_update_my_name_and_avatar(self, admin_session):
        # Capture original to restore later
        original_name = admin_session.admin_user.get("name")
        new_name = f"Admin {uuid.uuid4().hex[:6]}"
        new_avatar = "https://example.com/avatar.png"

        r = admin_session.put(
            f"{BASE_URL}/api/auth/me",
            json={"name": new_name, "avatar_url": new_avatar},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == new_name
        assert body["avatar_url"] == new_avatar
        assert "password_hash" not in body

        # Verify persistence via GET /api/auth/me
        g = admin_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert g.status_code == 200
        assert g.json()["name"] == new_name
        assert g.json()["avatar_url"] == new_avatar

        # Restore
        if original_name:
            r2 = admin_session.put(
                f"{BASE_URL}/api/auth/me",
                json={"name": original_name, "avatar_url": None},
                timeout=15,
            )
            assert r2.status_code == 200

    def test_update_me_requires_auth(self):
        r = requests.put(
            f"{BASE_URL}/api/auth/me",
            json={"name": "anon"},
            timeout=10,
        )
        assert r.status_code == 401


# ---------- Change password validation ----------

class TestChangePasswordValidation:
    def test_change_password_wrong_current_rejected(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/auth/change-password",
            json={"current_password": "definitely-not-the-password", "new_password": "newPW123!"},
            timeout=15,
        )
        assert r.status_code == 400, r.text
        # Admin password unchanged: verify login still works
        s = requests.Session()
        chk = s.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert chk.status_code == 200


# ---------- Forgot / reset password ----------

class TestForgotResetPassword:
    def test_forgot_password_always_ok(self):
        # existing email
        r1 = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": ADMIN_EMAIL},
            timeout=15,
        )
        assert r1.status_code == 200
        assert r1.json().get("ok") is True
        # non-existent email -> still ok (no user enumeration)
        r2 = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": f"noone_{uuid.uuid4().hex[:6]}@example.com"},
            timeout=15,
        )
        assert r2.status_code == 200
        assert r2.json().get("ok") is True

    def test_reset_password_full_flow(self, admin_session):
        """Create a temp user -> trigger forgot-password -> grab the latest unused
        token from the DB via the admin API surface (we use Mongo directly through
        a small in-process helper since there's no /admin/tokens endpoint)."""
        # Create a temp user via admin
        email = f"reset_{uuid.uuid4().hex[:8]}@example.com"
        original_pw = "ResetMe123!"
        new_pw = "ResetMeBetter456!"

        cu = admin_session.post(
            f"{BASE_URL}/api/users",
            json={"email": email, "password": original_pw, "name": "Reset User", "role": "user"},
            timeout=15,
        )
        assert cu.status_code in (200, 201), cu.text
        user_id = cu.json()["id"]

        try:
            # Trigger forgot-password
            fp = requests.post(
                f"{BASE_URL}/api/auth/forgot-password",
                json={"email": email},
                timeout=15,
            )
            assert fp.status_code == 200

            # Read the token directly from MongoDB (test helper)
            import asyncio as _asyncio
            from motor.motor_asyncio import AsyncIOMotorClient
            from dotenv import load_dotenv as _ld
            _ld("/app/backend/.env")

            async def fetch_token():
                client = AsyncIOMotorClient(os.environ["MONGO_URL"])
                db = client[os.environ["DB_NAME"]]
                doc = await db.password_reset_tokens.find_one(
                    {"user_id": user_id, "used": False},
                    sort=[("created_at", -1)],
                )
                client.close()
                return doc

            doc = _asyncio.run(fetch_token())
            assert doc is not None and doc.get("token"), "No reset token found in DB"
            token = doc["token"]

            # Reset with valid token
            rp = requests.post(
                f"{BASE_URL}/api/auth/reset-password",
                json={"token": token, "new_password": new_pw},
                timeout=15,
            )
            assert rp.status_code == 200, rp.text

            # Old password no longer works
            old = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": email, "password": original_pw},
                timeout=15,
            )
            assert old.status_code == 401

            # New password works
            new_login = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": email, "password": new_pw},
                timeout=15,
            )
            assert new_login.status_code == 200, new_login.text

            # Re-using the same token should fail (used)
            reuse = requests.post(
                f"{BASE_URL}/api/auth/reset-password",
                json={"token": token, "new_password": "another1"},
                timeout=15,
            )
            assert reuse.status_code == 400

        finally:
            admin_session.delete(f"{BASE_URL}/api/users/{user_id}", timeout=15)

    def test_reset_password_invalid_token_rejected(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/reset-password",
            json={"token": "this-token-does-not-exist", "new_password": "whatever1"},
            timeout=15,
        )
        assert r.status_code == 400


# ---------- Branding ----------

class TestBranding:
    def test_get_branding_public_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/branding", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        # Required keys regardless of whether saved or default
        for k in ["brand_name", "tagline", "hero_heading", "hero_subheading", "logo_url", "hero_image_url"]:
            assert k in body, f"missing branding key: {k}"

    def test_put_branding_admin_updates_and_get_reflects(self, admin_session):
        unique = uuid.uuid4().hex[:6]
        payload = {
            "brand_name": f"TEST_BRAND_{unique}",
            "tagline": f"TEST tagline {unique}",
            "hero_heading": f"TEST heading {unique}",
            "hero_subheading": f"TEST subheading {unique}",
            "logo_url": f"https://example.com/logo_{unique}.png",
            "hero_image_url": f"https://example.com/hero_{unique}.jpg",
        }
        # Capture current to restore later
        before = requests.get(f"{BASE_URL}/api/branding", timeout=15).json()

        try:
            r = admin_session.put(f"{BASE_URL}/api/branding", json=payload, timeout=15)
            assert r.status_code == 200, r.text
            body = r.json()
            for k, v in payload.items():
                assert body[k] == v, f"{k} not merged: {body.get(k)} != {v}"

            # Verify via public GET
            g = requests.get(f"{BASE_URL}/api/branding", timeout=15)
            assert g.status_code == 200
            for k, v in payload.items():
                assert g.json()[k] == v

            # Partial update only changes that field; others remain
            partial = {"tagline": f"PARTIAL_{unique}"}
            r2 = admin_session.put(f"{BASE_URL}/api/branding", json=partial, timeout=15)
            assert r2.status_code == 200
            merged = r2.json()
            assert merged["tagline"] == partial["tagline"]
            assert merged["brand_name"] == payload["brand_name"]  # unchanged
        finally:
            # Restore to whatever was there before this test
            restore = {k: before.get(k) for k in payload.keys()}
            # Filter out None so PUT doesn't error on "no fields"
            restore = {k: v for k, v in restore.items() if v is not None}
            if restore:
                admin_session.put(f"{BASE_URL}/api/branding", json=restore, timeout=15)

    def test_put_branding_non_admin_forbidden(self, admin_session):
        # Create a non-admin user, login as them, attempt PUT
        email = f"brand_user_{uuid.uuid4().hex[:6]}@example.com"
        password = "BrandUser123!"
        cu = admin_session.post(
            f"{BASE_URL}/api/users",
            json={"email": email, "password": password, "name": "Brand User", "role": "user"},
            timeout=15,
        )
        assert cu.status_code in (200, 201)
        uid = cu.json()["id"]
        try:
            ns = requests.Session()
            ns.headers.update({"Content-Type": "application/json"})
            login = ns.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": email, "password": password},
                timeout=15,
            )
            assert login.status_code == 200
            ns.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
            r = ns.put(
                f"{BASE_URL}/api/branding",
                json={"brand_name": "HACKED"},
                timeout=15,
            )
            assert r.status_code == 403, r.text
        finally:
            admin_session.delete(f"{BASE_URL}/api/users/{uid}", timeout=15)

    def test_put_branding_unauth_blocked(self):
        r = requests.put(
            f"{BASE_URL}/api/branding",
            json={"brand_name": "anon"},
            timeout=10,
        )
        assert r.status_code == 401
