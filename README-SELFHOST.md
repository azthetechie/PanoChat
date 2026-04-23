# Panorama Comms — Self-Hosted Setup

A self-hosted secure business chat (text + images + memes + GIFs) with an admin
dashboard (user management, channel management, and message moderation).

## Stack
- FastAPI + MongoDB (WebSockets for real-time)
- React (production build served by nginx)
- JWT auth with bcrypt, httpOnly cookies + Bearer token
- Local filesystem for uploads (persisted in Docker volume)
- Giphy (and optional Tenor) for GIF search

## 1. Requirements on your server
- Docker Engine 24+
- Docker Compose plugin (v2)
- Open port 80 (or whatever you set in `WEB_PORT`)

## 2. Configure
Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
# REQUIRED:
python3 -c "import secrets; print(secrets.token_hex(32))"   # put the output into JWT_SECRET
# Change ADMIN_PASSWORD to something strong
# (Optional) paste GIPHY_API_KEY to enable GIF search
nano .env
```

## 3. Start
```bash
docker compose up -d --build
```

This launches three containers: `mongo`, `backend`, and `frontend` (nginx). The
nginx container is the single public entrypoint; it serves the React app and
proxies `/api/*` (including WebSocket `/api/ws`) to the backend service.

## 4. First login
Browse to `http://<your-server-ip>/` and sign in as:
- email: `operations@panoramacoaches.com.au`
- password: the one you set in `.env` (default `Pano3666`)

Then head to the **Admin console** (sidebar) and:
1. Create teammate accounts (Users tab → New user).
2. Create additional channels, toggle private/public, manage members.
3. Hide / unhide / delete messages from the Moderation tab.

## 5. Production tips
- Put it behind HTTPS (nginx reverse-proxy + certbot, Caddy, or Cloudflare Tunnel).
  HttpOnly cookies are served with `Secure` + `SameSite=none`, so HTTPS is required
  for cross-origin cookies. For **same-origin** (everything on the same hostname),
  it works over HTTP too.
- Back up the `mongo_data` and `uploads_data` Docker volumes.
- Rotate `JWT_SECRET` to force all sessions to re-login.
- Change `ADMIN_PASSWORD` on first login: Admin → Users → yourself → … or just use
  the "Change password" endpoint.

## 6. Update
```bash
git pull
docker compose up -d --build
```

## 7. Useful endpoints
All under `/api`:
- `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- `GET/POST/PATCH/DELETE /channels`
- `GET/POST /messages/channel/{id}`, `POST /messages/{id}/hide`
- `POST /uploads/image` (multipart)
- `GET /giphy/search?q=...`, `GET /giphy/trending`
- `WS /api/ws?token=...`

## 8. Troubleshooting
- Service logs: `docker compose logs -f backend`, `docker compose logs -f frontend`
- Reset the DB: `docker compose down -v` (⚠️ deletes all data & uploads)
- Admin password rotate in `.env` then `docker compose up -d` — the startup
  seeder will sync the hash.
