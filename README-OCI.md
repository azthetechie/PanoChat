# Deploying Panorama Comms on Oracle Cloud Infrastructure (OCI)

This guide walks through running Panorama Comms on a single OCI compute
instance with **Caddy as the HTTPS reverse proxy** in front of the FastAPI
backend and the React frontend. You bring your own MongoDB.

> **Why Caddy?** It auto-renews TLS certificates, supports both Let's Encrypt
> (for real domains) and self-signed certs (for IP-only deploys), and adds
> WebSocket pass-through for our real-time chat with no extra config.

---

## 1 · Provision an OCI compute instance

1. **OCI Console** → Compute → Instances → **Create instance**.
2. Image: **Canonical Ubuntu 22.04** (or Oracle Linux 9).
3. Shape: `VM.Standard.E2.1.Micro` (Always Free) is enough for ~30 users.
   Bump to `VM.Standard.A1.Flex` (1 OCPU, 6 GB) for production.
4. Networking: pick the default VCN. **Add a public IP** (ephemeral is fine).
5. SSH: paste your public key.
5. **After the instance boots**, edit the **Subnet → Security List → Add Ingress Rules**:
   - TCP **80**  (Let's Encrypt HTTP-01 challenge + HTTP→HTTPS redirect)
   - TCP **443** (HTTPS)

   And **inside the VM**, open the same ports in the OS firewall.

   **Oracle Linux / RHEL (firewalld):**
   ```bash
   sudo firewall-cmd --permanent --add-service=http
   sudo firewall-cmd --permanent --add-service=https
   sudo firewall-cmd --reload
   ```

   **Ubuntu / Debian (iptables-persistent):**
   ```bash
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80  -j ACCEPT
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save
   ```

## 2 · Install Docker

```bash
ssh ubuntu@<your-vm-ip>

sudo apt update
sudo apt install -y ca-certificates curl gnupg git

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
   https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
exit  # log back in for the group to take effect
```

## 3 · Pull the code and configure

```bash
ssh ubuntu@<your-vm-ip>
git clone https://your-git-host/panorama-comms.git
cd panorama-comms

cp .env.oci.example .env
nano .env
```

**Fill in:**

| Variable | Required | Notes |
|---|---|---|
| `MONGO_URL` | ✅ | Default `mongodb://mongo:27017` works (Mongo runs in compose). Set to a different URI only if you want an external Mongo. |
| `DB_NAME` | ✅ | e.g. `panorama_comms` |
| `JWT_SECRET` | ✅ | `openssl rand -hex 32` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | ✅ | First admin (created on first boot) |
| `CADDY_HOST` | ✅ | Real domain (Let's Encrypt) → `chat.mycompany.com`. IP-only → `:443` (also uncomment `tls internal` in Caddyfile). |
| `ACME_EMAIL` | recommended | Real email for Let's Encrypt cert renewal alerts. |
| `FRONTEND_URL` | ✅ | `https://chat.mycompany.com` for domain; blank for IP only. |
| `GIPHY_API_KEY` | optional | https://developers.giphy.com |
| `RESEND_API_KEY` | optional | https://resend.com (password-reset emails) |

## 4a · TLS with a real domain (recommended)

1. Create a DNS **A record**: `chat.mycompany.com → <your-vm-ip>` and wait for
   propagation (use `dig chat.mycompany.com` or `nslookup chat.mycompany.com`).
2. Verify TCP **80 AND 443** are open in OCI Security List + the VM firewall (§1).
3. In `.env`:
   ```
   CADDY_HOST=chat.mycompany.com
   ACME_EMAIL=admin@mycompany.com
   FRONTEND_URL=https://chat.mycompany.com
   COOKIE_SAMESITE=lax
   COOKIE_SECURE=true
   ```
4. Caddy will fetch a Let's Encrypt cert automatically on first boot. Watch
   the logs: `docker compose -f docker-compose.oci.yml logs -f caddy` — you
   should see `certificate obtained successfully` from issuer `acme-v02`.

## 4b · TLS with IP only (no domain)

Let's Encrypt **cannot** issue certs for raw IPs, so we use Caddy's built-in CA
to sign a self-signed cert. Browsers will show a one-time warning the first
time each user visits — they can click through ("Advanced → Proceed").

1. Edit `Caddyfile` — uncomment the `tls internal` line inside the site block.
2. In `.env`:
   ```
   CADDY_HOST=:443
   ACME_EMAIL=admin@example.com
   FRONTEND_URL=
   COOKIE_SAMESITE=lax
   COOKIE_SECURE=true
   ```
3. Open `https://<your-vm-ip>` in the browser → accept the warning once.

> ⚠️  If you want zero browser warnings without a real domain, get a free
> subdomain from DuckDNS or Cloudflare and use §4a — it's the cleanest path.

## 5 · Launch

```bash
docker compose -f docker-compose.oci.yml --env-file .env up -d --build
```

Check logs:
```bash
docker compose -f docker-compose.oci.yml logs -f
```

You should see Caddy pull a cert, the backend log `Startup complete. Admin
seeded.` and the frontend container ready.

Open `https://<your-host-or-ip>` in your browser, log in with your
`ADMIN_EMAIL` / `ADMIN_PASSWORD`. Done.

## 6 · Day-2 ops

```bash
# Update to latest code
git pull
docker compose -f docker-compose.oci.yml up -d --build

# View live logs
docker compose -f docker-compose.oci.yml logs -f backend

# Restart everything
docker compose -f docker-compose.oci.yml restart

# Stop
docker compose -f docker-compose.oci.yml down
```

**Persistent data lives in Docker volumes:**
- `mongo_data` — MongoDB database
- `uploads_data` — uploaded images and GIF picks
- `caddy_data`, `caddy_config` — TLS certs, cached state

Back them up with `docker run --rm -v mongo_data:/data -v $(pwd):/backup
alpine tar czf /backup/mongo.tgz /data` periodically.

## 7 · Troubleshooting

### "Not authenticated" after login

This was a known cookie issue. The current build:
- Sends `Authorization: Bearer <token>` on every API call from the SPA, so cookies are no longer required for auth to work.
- Auto-relaxes cookie `SameSite` to `lax` when `FRONTEND_URL` is blank or HTTP, so plain-HTTP same-origin deploys also work.

If you still see 401s:
1. Open the browser DevTools → Application → Local Storage → check for `access_token`.
2. Network tab → confirm the `Authorization: Bearer ...` header is on `/api/auth/me`.
3. Logs: `docker compose -f docker-compose.oci.yml logs backend | grep auth`.

### WebSocket fails to connect

Caddy already handles the upgrade. Check that:
- Your firewall (OCI Security List + iptables) allows TCP 443.
- `FRONTEND_URL` matches the URL you actually visit (or is left blank for same-origin).

### Resend emails not sending

- Verify `RESEND_API_KEY` in `.env`.
- Verify the sender domain in Resend Dashboard (free `onboarding@resend.dev` works without verification but only sends to YOUR Resend account email).
- Backend logs will show `Sender validation skipped: ...` if domain isn't verified — emails will fall back to stdout logs in that case.

### Force-rotate JWT secret

Edit `.env` → `JWT_SECRET=...` → `docker compose ... up -d`. Existing user
sessions will be invalidated and everyone re-logs in.

---

## Architecture summary

```
Browser
  │ HTTPS :443
  ▼
Caddy (auto-TLS)
  ├─ /api/*  →  backend  (FastAPI :8001)  ──► mongo (:27017)
  └─ /*      →  frontend (nginx :80, static React)
                   │
                   └─ /api/* (relative) → handled by Caddy ↑
```

All containers run on a private Docker network. Only Caddy is exposed to the
public internet. Mongo is internal-only.
