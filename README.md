# Archipelago Pie

> Archipelago Multiworld YAML collector and lobby manager. Hosted at **[ap-pie.com](https://ap-pie.com)**.

Archipelago Pie lets a host create a room, share a public link with their players, collect everyone's YAMLs in one place, and hand off the bundle to an Archipelago multiworld generator. Inspired by Bananium's flow, with a focus on the YAML-collection front of the multiworld lifecycle - generation and live hosting are intentionally out of scope for the MVP.

## What ships in v1

- **Discord login** for hosts (admin-approved). Players can submit anonymously, or hosts can require Discord login to know who uploaded what.
- **Public room landing pages** at `/r/<id>` - players drop YAMLs (drag-and-drop or paste), see what's been submitted, download single files or the whole bundle.
- **Host dashboard** at `/rooms/<id>` - manage uploads, validate, search/sort the YAML table, see uploader Discord identity, reopen closed rooms, point a room at an external Archipelago server.
- **Validation** of submitted YAMLs against installed apworlds, with host overrides for "trust me, this is fine" cases.

## Out of scope for v1

- Hosting the live Archipelago server (rooms point at an external `host:port` the host runs themselves).
- Generation of multiworld seeds (admins only - the MVP is a YAML collector).
- Item market, tracker, public game list - admin-only functionality, hidden from regular users.

## Stack

- **Backend**: Python 3.12, Flask, gunicorn, PostgreSQL 17. See [`ap-web/`](ap-web/).
- **Frontend**: React 18, TypeScript, Vite. See [`ap-web/frontend/`](ap-web/frontend/).
- **Deployment**: Docker Compose (postgres + ap-web containers), Caddy in front for TLS.
- **Auth**: Discord OAuth2 with admin approval gate.

## Quick start (local dev)

```bash
# Clone
git clone https://github.com/dowlle/ap-pie.git
cd ap-pie

# Configure
cp .env.example .env
# Fill in DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, SECRET_KEY, POSTGRES_PASSWORD

# Install Archipelago binary (needed only if you want generation)
bash scripts/fetch-archipelago.sh

# Bring it up
docker compose up --build -d

# Open http://localhost:5001
```

## Deployment (production)

See [`deploy.sh`](deploy.sh) for the deploy story. In short: SSH-key access to your VPS, docker + docker compose installed, `git pull && docker compose up --build -d`. Caddy in front handles TLS via Let's Encrypt:

```caddyfile
ap-pie.com {
    reverse_proxy localhost:5001
}
```

## Discord OAuth setup

1. Go to https://discord.com/developers/applications and create a new application.
2. OAuth2 → Add redirect URI: `https://your-host/api/auth/callback` (and `http://localhost:5001/api/auth/callback` if developing locally).
3. Copy the Client ID and Client Secret into your `.env`.
4. Get your own Discord user ID (Developer Mode on, right-click name → Copy User ID) and put it in `AP_OWNER_DISCORD_ID` to auto-promote yourself to admin on first login.

## Configuration reference

See [`.env.example`](.env.example) for the full list of environment variables.

## License

MIT - see [LICENSE](LICENSE).
