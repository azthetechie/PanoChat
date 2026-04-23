# Panorama Comms — PRD

## Original problem statement
> Build me a communication solution for business, Text chat with the ability to include
> pictures memes gifs. add a dashboard to the back end that includes user management,
> channel management and the ability for admins to hide messages. make it user based
> authentication but secure and ensure i can deploy this on a self hosted server not
> emergents online deploy.
>
> Follow-up: user self-management (display name, password, reset) + admin-configurable
> branding (logo + hero image) applied to the login screen.

## Architecture
- **Backend**: FastAPI + Motor (MongoDB) + PyJWT + bcrypt + httpx + WebSockets
- **Frontend**: React 19 (CRA + craco) + Tailwind + shadcn primitives + lucide-react
- **Realtime**: WebSocket (/api/ws) — per-channel subscribe, JSON events
- **Storage**: Local filesystem for uploads (persisted Docker volume)
- **Auth**: JWT (HS256) in httpOnly cookies + Bearer header (for cross-origin previews). bcrypt hashing. Brute-force protection (per-IP via X-Forwarded-For + email-only secondary counter).
- **Self-host**: Dockerfile.backend + Dockerfile.frontend + docker-compose.yml (mongo + backend + nginx-frontend). Full setup guide in `/app/README-SELFHOST.md`.

## Core requirements (static)
- User-based auth (secure, JWT + bcrypt), admin-controlled account creation.
- Text chat with image + GIF + "meme" (uploaded image) attachments.
- Channels (public/private), admin-managed members, archive.
- Admin dashboard: Users CRUD, Channels CRUD, Message moderation (hide/unhide/delete, search).
- User self-service: change name/avatar, change password, forgot/reset password.
- Admin-editable branding: logo + hero image + copy applied to login screen.
- Self-hostable via Docker (no Emergent dependencies at runtime).

## User personas
1. **Operations admin** (`operations@panoramacoaches.com.au`) — seeds & manages users/channels/branding, moderates messages.
2. **Team member** — signs in, chats, uploads media, updates own profile.

## Status of implementation (Feb 2026)
### Completed
- Auth: login, logout, /me, refresh, register (admin), change-password, forgot/reset-password ✅
- **Password-reset email via Resend** (falls back to stdout log if unconfigured or Resend API returns error) ✅
- Brute-force lockout working behind ingress (X-Forwarded-For + email-only counter) ✅
- Users CRUD (admin) with self-protection (can't delete/demote/deactivate self) ✅
- Channels CRUD (admin), members add/remove, archive ✅
- 1:1 Direct Messages — auto-created on first message; DMs excluded from channel list; separate sidebar section; **partial unique index** on `channels.name` where `type='dm'` (race-safe) ✅
- Messages: create/list/delete, hide/unhide (admin), moderation search ✅
- **Message threads** — `POST /api/messages/{id}/react`, thread panel (desktop side + mobile drawer), denorm `thread_reply_count` + `thread_last_reply_at` on parent, WS `thread:reply` broadcast ✅
- @Mentions — autocomplete popover in composer; highlighted row + inline `@Name` styling; mentions-me badge ✅
- Reactions — per-message emoji toggles; chips below message; realtime broadcast ✅
- Desktop notifications (DMs + @mentions only; respects quiet hours + snooze) ✅
- **Mute / quiet hours** — client-side: snooze 1h/8h/24h/until 9 AM; daily quiet-hours window ✅
- File uploads (PNG/JPG/GIF/WebP, 15MB cap) + static serving ✅
- Giphy search + trending ✅
- WebSocket real-time broadcasts (message:new, :hidden, :unhidden, :deleted, :reactions, thread:reply) ✅
- Profile page (name, avatar, password change, reset-link request, notifications toggle, snooze, quiet hours) ✅
- Admin Branding tab (logo + hero image + copy + live preview) ✅
- Unread counters per channel + DM (sidebar badge; auto-mark-read on open/focus/send) ✅
- Mobile-friendly layout (off-canvas sidebar drawer + hamburger; admin tabs horizontal-scroll; responsive headers) ✅
- Swiss Brutalist UI (Bricolage Grotesque + Manrope, #FF5A00 signal, rounded-none) ✅
- Docker: Dockerfile.backend, Dockerfile.frontend (nginx with WS proxy), docker-compose.yml, .env.example ✅
- README-SELFHOST.md with first-login + production tips ✅
- Backend tests: **89/89** pytest passing ✅
- Frontend E2E: comprehensive Playwright coverage including thread end-to-end + quiet-hours UI ✅

### Not implemented (deferred)
- P1: SMTP/SES email delivery for password reset (currently logs link to backend stdout)
- P1: Direct/1:1 messages (only public/private channels today)
- P1: Notifications (desktop/native/unread badges)
- P2: Message reactions & threads
- P2: Magic-byte MIME validation on uploads (extension-only today)
- P2: Password strength policy (min 6 char today)
- P2: Audit log for admin actions

## Prioritized backlog
- **P0** — none outstanding (all critical features ship)
- **P1** — Email delivery for password reset; unread badges per channel; DMs
- **P2** — Reactions; threads; audit log; stronger upload validation; password policy

## Next tasks
- Wire forgot-password to SMTP (Resend/SendGrid) once email provider chosen
- Add unread message counters per channel in the sidebar
- Add 1:1 DMs (new `dm` channel type, auto-created on first message)

## Deploy
`cp .env.example .env`, edit secrets, `docker compose up -d --build`. See `README-SELFHOST.md`.
