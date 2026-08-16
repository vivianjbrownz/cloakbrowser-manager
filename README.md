<p align="center">
<img src="https://i.imgur.com/cqkp6fG.png" width="500" alt="CloakBrowser">
</p>

<h3 align="center">Browser Profile Manager for CloakBrowser</h3>

<p align="center">
Create, manage, and launch isolated browser profiles with unique fingerprints.<br>
Free, self-hosted alternative to Multilogin, GoLogin, and AdsPower.
</p>

<p align="center">
<a href="https://github.com/CloakHQ/CloakBrowser"><img src="https://img.shields.io/github/stars/cloakhq/cloakbrowser?label=CloakBrowser" alt="Stars"></a>
<a href="https://github.com/stevenbbrooksz/cloakbrowser-manager/pkgs/container/cloakbrowser-manager"><img src="https://img.shields.io/badge/container-ghcr.io-blue?logo=github" alt="Container"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
</p>

---

<p align="center">
<img src="https://i.imgur.com/twdX81Q.png" width="800" alt="CloakBrowser Manager — Browser View">
<br>
<img src="https://i.imgur.com/XFYn1qY.png" width="800" alt="CloakBrowser Manager — Profile Settings">
</p>

Each profile is an isolated CloakBrowser instance with its own fingerprint, proxy, cookies, and session data. Profiles persist across restarts. Everything runs in one Docker container. Running profiles with no UI/VNC or CDP connection sleep after 20 minutes; under 2 GiB available memory, disconnected profiles become eligible after 2 minutes. Sleeping preserves the profile fingerprint and session data.

## BeginOS Inventory Build

This working tree is a custom BeginOS build of CloakBrowser Manager. It keeps the upstream browser profile features and adds an Inventory table for operating dozens of profiles and social account records.

The deployed production image is:

```text
ghcr.io/stevenbbrooksz/cloakbrowser-manager:inventory-20260623
```

Inventory behavior:

- The Inventory table is the default main view after login.
- The Manager UI supports `System`, `Light`, and `Dark` panel themes stored in local browser storage.
- One browser profile can have multiple account asset records.
- Profiles with no account assets appear as profile-only rows.
- Account asset statuses are `new`, `warming`, `active`, `limited`, `blocked`, and `retired`.
- Retired accounts are hidden by default.
- Passwords, 2FA secrets, TOTP seeds, and recovery codes are intentionally not stored.
- CSV import rejects sensitive columns such as `password`, `2fa_secret`, `totp`, and `recovery_code`.

Inventory API:

```text
GET    /api/inventory/rows?include_retired=false
GET    /api/inventory/export.csv
POST   /api/inventory/import.csv?dry_run=true|false
POST   /api/profiles/{profile_id}/accounts
PUT    /api/accounts/{account_id}
DELETE /api/accounts/{account_id}
```

CSV columns:

```text
profile_id,profile_name,proxy,account_id,platform,account_identifier,email_or_phone,account_status,platform_status_detail,purpose,last_used_at,notes,tags
```

Import matching rules:

- Existing rows with `account_id` are updated when the account belongs to `profile_id`.
- Rows without `account_id` match by `(profile_id, platform, account_identifier)`.
- Unknown `profile_id` rows are rejected.
- Run `dry_run=true` before applying imports.

### Install with Docker

```bash
docker run -d --name cloakbrowser-manager \
  -p 127.0.0.1:8080:8080 \
  -v cloakprofiles:/data \
  -e AUTH_TOKEN='replace-with-a-long-random-token' \
  ghcr.io/stevenbbrooksz/cloakbrowser-manager:inventory-20260623
```

Keep the `127.0.0.1` binding when you expose the Manager through SSH tunneling or a HTTPS reverse proxy. Only bind directly to a public interface if you have network controls and HTTPS in front of it.

Or build from source:

```bash
git clone https://github.com/stevenbbrooksz/cloakbrowser-manager.git
cd cloakbrowser-manager
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080) in your browser. Create a profile. Click Launch. Done.

> **Early alpha** — this project is under active development. Expect bugs. If you find one, please [open an issue](https://github.com/stevenbbrooksz/cloakbrowser-manager/issues).

## Why Not Just Use a VPN?

A VPN only changes your IP. Incognito only clears cookies. Chrome profiles share the same hardware fingerprint underneath. Platforms use 50+ signals to link your accounts — canvas, WebGL, audio, GPU, fonts, screen size, timezone.

Each CloakBrowser profile generates a completely different device identity. To the website, each profile looks like a different computer.

| Solution | What it changes | Accounts linked? |
|----------|----------------|-----------------|
| VPN | IP address only | Yes — same fingerprint |
| Incognito | Clears cookies | Yes — same fingerprint |
| Chrome profiles | Separate bookmarks/cookies | Yes — same hardware fingerprint |
| **CloakBrowser** | **Everything — full device identity per profile** | **No** |

## Features

- **Profile management** — create, edit, delete browser profiles with unique fingerprints
- **Per-profile settings** — fingerprint seed, proxy, timezone, locale, user agent, screen size, platform
- **One-click launch/stop** — each profile runs as an isolated CloakBrowser instance
- **Session persistence** — cookies, localStorage, and cache survive browser restarts
- **In-browser viewing** — interact with launched browsers via noVNC, directly in the web GUI
- **Playwright/Puppeteer API** — connect to any running profile programmatically via CDP, while still watching it live in the browser
- **Optional authentication** — protect the web UI and API with a single token, or run wide open locally
- **Powered by CloakBrowser** — 32 source-level C++ patches, passes Cloudflare Turnstile, 0.9 reCAPTCHA v3 score

## Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + Tailwind CSS
- **Browser viewer**: noVNC (WebSocket-based VNC client)
- **Database**: SQLite
- **Browser engine**: [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) (stealth Chromium binary)

## Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker compose up --build
```

## Requirements

- Docker (20.10+)
- ~2 GB disk (image + binary)
- ~512 MB RAM per running profile

## Updating

For this BeginOS Inventory build, pull the latest published image and recreate the container:

```bash
docker pull ghcr.io/stevenbbrooksz/cloakbrowser-manager:inventory-20260623
docker stop cloakbrowser-manager
docker rm cloakbrowser-manager
docker run -d --name cloakbrowser-manager \
  -p 127.0.0.1:8080:8080 \
  -v cloakprofiles:/data \
  -e AUTH_TOKEN='replace-with-the-existing-token' \
  ghcr.io/stevenbbrooksz/cloakbrowser-manager:inventory-20260623
```

Your profiles and session data are stored in the `cloakprofiles` volume and persist across updates.

Do not deploy upstream `cloakhq/cloakbrowser-manager:latest` unless you intentionally want to remove the Inventory feature. When maintaining this custom build:

1. Back up `/opt/cloakbrowser-manager/.env` and the `cloakprofiles` Docker volume.
2. Merge upstream changes into this custom working tree.
3. Run backend and frontend tests.
4. Build a dated image tag:

```bash
docker build --build-arg TARGETARCH=amd64 \
  -t ghcr.io/stevenbbrooksz/cloakbrowser-manager:inventory-YYYYMMDD .
```

5. Recreate the container with the same `AUTH_TOKEN` and `cloakprofiles:/data` volume.
6. Verify `/api/status`, `/api/inventory/rows`, CSV export, and one profile launch.

## Automation API

Every running profile exposes a CDP (Chrome DevTools Protocol) endpoint. Connect Playwright or Puppeteer to automate a profile while watching it live in the browser.

```python
from playwright.async_api import async_playwright

async with async_playwright() as pw:
    browser = await pw.chromium.connect_over_cdp(
        "http://localhost:8080/api/profiles/<profile-id>/cdp"
    )
    page = browser.contexts[0].pages[0]
    await page.goto("https://example.com")
```

```javascript
const { chromium } = require("playwright");

const browser = await chromium.connectOverCDP(
  "http://localhost:8080/api/profiles/<profile-id>/cdp"
);
const page = browser.contexts()[0].pages()[0];
await page.goto("https://example.com");
```

The CDP URL is available in the toolbar (code icon) when a profile is running. The same browser session is accessible both visually through VNC and programmatically through the API.

## Remote Access

The container binds to localhost only. To access from a remote server:

```bash
ssh -L 8080:localhost:8080 your-server
```

Then open `http://localhost:8080`.

## Authentication

By default, there is no authentication (ideal for local use). To protect the web UI and API when hosting on a network, set the `AUTH_TOKEN` environment variable:

```bash
docker run -p 127.0.0.1:8080:8080 \
  -v cloakprofiles:/data \
  -e AUTH_TOKEN=your-secret-token \
  ghcr.io/stevenbbrooksz/cloakbrowser-manager:inventory-20260623
```

Or in `docker-compose.yml`:

```yaml
environment:
  - AUTH_TOKEN=your-secret-token
```

When `AUTH_TOKEN` is set:

- The web UI shows a login page. Enter the token to unlock.
- API consumers pass the token via `Authorization: Bearer <token>` header.
- VNC WebSocket connections are authenticated via the login cookie.
- The `/api/status` endpoint remains unauthenticated (for Docker healthcheck).

> **Note**: The auth token is transmitted in cleartext over HTTP. If you expose the Manager to the internet, put it behind a reverse proxy with HTTPS (Caddy, nginx, Traefik).

## License

- **This application** (GUI source code) — MIT. See [LICENSE](LICENSE).
- **CloakBrowser binary** (compiled Chromium) — free to use, no redistribution. See [BINARY-LICENSE.md](BINARY-LICENSE.md).

The GUI application requires the CloakBrowser Chromium binary to function. The binary is automatically downloaded on first launch and is governed by its own license terms. If you fork or redistribute this application, your users must comply with the [CloakBrowser Binary License](BINARY-LICENSE.md).

## Contributing

Contributions are welcome. Please [open an issue](https://github.com/stevenbbrooksz/cloakbrowser-manager/issues) first to discuss what you'd like to change.

## Links

- **CloakBrowser** — [github.com/CloakHQ/CloakBrowser](https://github.com/CloakHQ/CloakBrowser)
- **BeginOS Inventory build** — [github.com/stevenbbrooksz/cloakbrowser-manager](https://github.com/stevenbbrooksz/cloakbrowser-manager)
- **Upstream Manager** — [github.com/CloakHQ/CloakBrowser-Manager](https://github.com/CloakHQ/CloakBrowser-Manager)
- **Website** — [cloakbrowser.dev](https://cloakbrowser.dev)
- **Bug reports** — [GitHub Issues](https://github.com/stevenbbrooksz/cloakbrowser-manager/issues)
- **Contact** — cloakhq@pm.me
