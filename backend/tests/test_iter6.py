"""Iter-6 tests: presence indicator + sender-domain validation + DM race regression."""
import asyncio
import json
import os
import time
import uuid
import pytest
import requests
import websockets

from conftest import BASE_URL, LOCAL_URL, ADMIN_EMAIL, ADMIN_PASSWORD


# ---------- Helpers ----------
def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"], r.json()["user"]


def _admin_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_ctx():
    tok, user = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return {"token": tok, "user": user, "headers": _admin_headers(tok)}


@pytest.fixture(scope="module")
def ephemeral_user(admin_ctx):
    """Create + cleanup a throwaway user (used to test presence for a non-admin)."""
    suffix = uuid.uuid4().hex[:6]
    email = f"iter6presence_{suffix}@example.com"
    password = "TestPass123!"
    r = requests.post(f"{BASE_URL}/api/users",
                      headers=admin_ctx["headers"],
                      json={"email": email, "name": f"Iter6 User {suffix}",
                            "password": password, "role": "user"},
                      timeout=15)
    assert r.status_code in (200, 201), r.text
    uid = r.json()["id"]
    tok, user = _login(email, password)
    yield {"id": uid, "token": tok, "user": user, "email": email}
    # cleanup
    try:
        requests.delete(f"{BASE_URL}/api/users/{uid}",
                        headers=admin_ctx["headers"], timeout=10)
    except Exception:
        pass


def _ws_url(token):
    # Local WS — preview ingress often strips upgrade headers
    return f"{LOCAL_URL.replace('http', 'ws')}/api/ws?token={token}"


async def _recv_until(ws, pred, timeout=3.0):
    """Receive messages until pred(evt) is true or timeout."""
    end = asyncio.get_event_loop().time() + timeout
    matched = []
    all_msgs = []
    while asyncio.get_event_loop().time() < end:
        remaining = end - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            break
        try:
            evt = json.loads(raw)
        except Exception:
            continue
        all_msgs.append(evt)
        if pred(evt):
            matched.append(evt)
            return matched, all_msgs
    return matched, all_msgs


# ---------- GET /api/presence ----------
class TestPresenceEndpoint:
    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/presence", timeout=10)
        assert r.status_code in (401, 403), r.status_code

    def test_returns_online_list(self, admin_ctx):
        r = requests.get(f"{BASE_URL}/api/presence",
                         headers=admin_ctx["headers"], timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "online" in body
        assert isinstance(body["online"], list)

    def test_caller_online_after_ws(self, admin_ctx):
        """Open a WS; GET /api/presence should then include the caller's id."""
        async def run():
            async with websockets.connect(_ws_url(admin_ctx["token"])) as ws:
                # wait for hello
                await asyncio.wait_for(ws.recv(), timeout=3.0)
                # Give the connect() presence broadcast a moment
                await asyncio.sleep(0.2)
                r = requests.get(f"{BASE_URL}/api/presence",
                                 headers=admin_ctx["headers"], timeout=10)
                assert r.status_code == 200
                assert admin_ctx["user"]["id"] in r.json()["online"]
        asyncio.run(run())


# ---------- WS presence:update broadcast ----------
class TestPresenceBroadcast:
    def test_new_ws_broadcasts_online_to_all(self, admin_ctx, ephemeral_user):
        async def run():
            # Admin observer socket
            async with websockets.connect(_ws_url(admin_ctx["token"])) as obs:
                await asyncio.wait_for(obs.recv(), timeout=3.0)  # hello
                # Drain any stale presence events
                await _recv_until(obs, lambda e: False, timeout=0.3)

                # User A connects — observer must see presence:update online
                async with websockets.connect(_ws_url(ephemeral_user["token"])) as a:
                    await asyncio.wait_for(a.recv(), timeout=3.0)  # a's hello
                    matched, _all = await _recv_until(
                        obs,
                        lambda e: e.get("type") == "presence:update"
                        and e.get("user_id") == ephemeral_user["id"]
                        and e.get("online") is True,
                        timeout=3.0,
                    )
                    assert matched, f"no presence:update online seen; got={_all}"
                # On close, observer should see offline
                matched_off, _all2 = await _recv_until(
                    obs,
                    lambda e: e.get("type") == "presence:update"
                    and e.get("user_id") == ephemeral_user["id"]
                    and e.get("online") is False,
                    timeout=3.0,
                )
                assert matched_off, f"no offline event after close; got={_all2}"
        asyncio.run(run())

    def test_two_sockets_same_user_no_offline_on_one_close(self, admin_ctx, ephemeral_user):
        async def run():
            async with websockets.connect(_ws_url(admin_ctx["token"])) as obs:
                await asyncio.wait_for(obs.recv(), timeout=3.0)
                await _recv_until(obs, lambda e: False, timeout=0.3)

                # Open two sockets for the ephemeral user
                a1 = await websockets.connect(_ws_url(ephemeral_user["token"]))
                await asyncio.wait_for(a1.recv(), timeout=3.0)
                # First socket triggers online (0->1)
                matched, _ = await _recv_until(
                    obs,
                    lambda e: e.get("type") == "presence:update"
                    and e.get("user_id") == ephemeral_user["id"]
                    and e.get("online") is True,
                    timeout=3.0,
                )
                assert matched, "expected initial online"

                a2 = await websockets.connect(_ws_url(ephemeral_user["token"]))
                await asyncio.wait_for(a2.recv(), timeout=3.0)
                # 1->2 transition should NOT emit a new presence event
                matched_extra, _ = await _recv_until(
                    obs,
                    lambda e: e.get("type") == "presence:update"
                    and e.get("user_id") == ephemeral_user["id"],
                    timeout=1.0,
                )
                assert not matched_extra, f"unexpected presence event on 2nd conn: {matched_extra}"

                # Close one socket — 2->1 transition; should NOT emit offline
                await a1.close()
                matched_off, _ = await _recv_until(
                    obs,
                    lambda e: e.get("type") == "presence:update"
                    and e.get("user_id") == ephemeral_user["id"]
                    and e.get("online") is False,
                    timeout=1.5,
                )
                assert not matched_off, f"offline emitted too early: {matched_off}"

                # Verify user still online via REST
                r = requests.get(f"{BASE_URL}/api/presence",
                                 headers=admin_ctx["headers"], timeout=10)
                assert ephemeral_user["id"] in r.json()["online"]

                # Close the last socket — must emit offline
                await a2.close()
                matched_off2, _all = await _recv_until(
                    obs,
                    lambda e: e.get("type") == "presence:update"
                    and e.get("user_id") == ephemeral_user["id"]
                    and e.get("online") is False,
                    timeout=3.0,
                )
                assert matched_off2, f"no offline after last close; got={_all}"
        asyncio.run(run())


# ---------- Sender-domain validation (log inspection) ----------
class TestSenderValidation:
    def _log_text(self):
        paths = [
            "/var/log/supervisor/backend.err.log",
            "/var/log/supervisor/backend.out.log",
        ]
        txt = ""
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", errors="ignore") as f:
                        txt += f.read()
                except Exception:
                    pass
        return txt

    def test_startup_validation_logged(self):
        txt = self._log_text()
        # Current config uses onboarding@resend.dev → test-sender info log
        assert "using Resend test sender" in txt or \
               "is verified with Resend" in txt or \
               "NOT verified with Resend" in txt or \
               "RESEND_API_KEY is empty" in txt, \
               "validate_sender_domain() did not emit any expected log line"

    def test_resend_dev_sender_is_info_not_warning(self):
        """With SENDER_EMAIL=onboarding@resend.dev it should log the INFO 'using Resend test sender' line."""
        sender = os.environ.get("SENDER_EMAIL", "").lower()
        if "resend.dev" not in sender:
            pytest.skip(f"SENDER_EMAIL is not a resend.dev address ({sender}) — cannot assert test-sender log")
        txt = self._log_text()
        assert "using Resend test sender" in txt

    def test_validate_sender_domain_never_raises(self):
        """Directly import and invoke — must return a dict regardless of config."""
        import sys
        sys.path.insert(0, "/app/backend")
        from email_service import validate_sender_domain
        out = validate_sender_domain()
        assert isinstance(out, dict)
        assert set(["configured", "sender", "domain", "verified", "warning", "domains"]).issubset(out.keys())


# ---------- DM race regression (iter5 — still holds after presence wiring) ----------
class TestDmRaceRegression:
    def test_concurrent_dm_open_returns_same_channel(self, admin_ctx, ephemeral_user):
        import threading
        other_id = ephemeral_user["id"]
        results = []

        def open_dm():
            r = requests.post(f"{BASE_URL}/api/dms",
                              headers=admin_ctx["headers"],
                              json={"user_id": other_id},
                              timeout=15)
            results.append(r)

        t1 = threading.Thread(target=open_dm)
        t2 = threading.Thread(target=open_dm)
        t1.start(); t2.start()
        t1.join(); t2.join()

        assert len(results) == 2
        for r in results:
            assert r.status_code in (200, 201), r.text
        ids = [r.json().get("id") or r.json().get("channel_id") for r in results]
        assert ids[0] and ids[0] == ids[1], f"race produced different DM ids: {ids}"
