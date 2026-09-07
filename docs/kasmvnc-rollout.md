# KasmVNC viewer rollout

The Manager can use either its existing noVNC compatibility client or the native
KasmVNC 1.3.3 client. Users continue to use the same website. The selector in the
viewer toolbar switches clients without restarting the browser or changing its
Profile. Existing quality, fullscreen, text clipboard and access controls remain.

## Interfaces and configuration

- `WS /api/profiles/{id}/vnc-native`: binary, unmodified KasmVNC transport. Uses
  the same authentication, Profile assignment, Origin validation and idle
  connection accounting as `/vnc`. No direct VNC ports or Kasm management APIs
  are exposed. WebRTC is disabled; the existing HTTPS/WebSocket ingress works.
- `GET /api/auth/status`: additive `viewer_default: "novnc" | "kasm"` field.
- `CLOAKBROWSER_VIEWER_DEFAULT=novnc` is the initial deployment default. A user's
  explicit toolbar selection (`cloakbrowser.viewer.implementation` in local
  storage) takes precedence. Change the server default to `kasm` only after the
  performance and stability gates below pass on the target deployment.
- Quality preference retains `cloakbrowser.viewer.qualityMode`. Native presets
  use Custom mode, 30 FPS, WebP and fixed remote geometry; Low/Static must not
  resize the desktop. Per-instance channels prevent cross-Profile input sharing.
- Disconnect retries: 1, 2, 4, 8, 8 seconds, checking the protected Profile status
  endpoint before each retry. A stable connection resets the budget after 30
  seconds. Access denied, removed/stopped Profile, or exhausted retries leaves
  the toolbar and manual reconnect available. It never launches/restarts Chrome.
- Text clipboard acknowledgements wait for xclip to own the selection before
  sending Ctrl+V. A failed clipboard write never pastes a stale remote selection.

## Verification

Run from the checkout:

```sh
python3 ops/verify_kasm_vendor.py
.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
```

The publish workflow requires these checks before publishing an image. Ordinary
releases use the digest pinned in `Dockerfile`, never `Dockerfile.full`. The
vendored client's source/patch hashes, licenses and version are recorded in
`frontend/src/vendor/kasmvnc/`.

`ops/qa_kasmvnc.py` creates its own temporary Profiles, runs a fixed page in real
CloakBrowser instances, connects through the actual Manager UI and removes only
those temporary Profiles in cleanup. Use an isolated volume first. A token file
must be private (mode 0600); do not put tokens in shell arguments or reports.

```sh
.venv/bin/python ops/qa_kasmvnc.py \
  --base-url http://127.0.0.1:18981 \
  --token-file /secure/path/manager-token \
  --output /secure/path/qa/report.json \
  --samples 50 --concurrency 1 3 --soak-seconds 1800
```

The measurement starts at the local input event and ends when the decoded canvas
changes, excluding the target site's network load. First-wheel initialization
is recorded separately; regular samples follow two initialization wheel events.
The first wheel event has sometimes produced no feedback on a fresh browser
with either client. XInput initialization is a hypothesis, not an established
root cause; mode order can affect this result. Do not present warmed-up numbers
as proof of first-interaction correctness.

Record the actual client's network/device, round-trip latency, CPU, memory and
frame rate alongside the JSON report. Automation on a server is not a substitute
for the user's network. Require P95 ≤800 ms **and** ≥50% improvement against
compatibility mode for each action in single- and three-Profile cases. Check
Chinese composition, paste without continuous sync, quality/fullscreen geometry,
session persistence, reconnect and a 30-minute stability run. If a gate fails,
leave compatibility as the default and retain KasmVNC as an explicit option.

## Narrow production release and rollback

Production preflight on 2026-09-07 confirmed KasmVNC 1.3.3-1, 13 Profiles, the
`cloakprofiles` data volume, `/opt/agentos/config:/run/agentos:ro`, scoped access
and **64 MiB** shared memory. Preserve the actual runtime configuration; do not
replace it with an outdated example `docker run --shm-size=2g` command. Browser
binary, 187 font files, Python packages and system package fingerprints matched
the pinned runtime base during preflight.

1. Publish/pull an immutable image and compare runtime fingerprints on current
   and candidate containers with `ops/runtime_fingerprint.py`. Verify KasmVNC is
   still 1.3.3. Keep this check outside the release transaction.
2. Copy `ops/release_viewer.py` to the Docker host. Its default operation is a
   read-only preflight. It obtains mounts, environment, limits, networks and
   restart policy from Docker, not a hard-coded replacement command.

```sh
python3 release_viewer.py --image ghcr.io/OWNER/cloakbrowser-manager@sha256:DIGEST
python3 release_viewer.py --image ghcr.io/OWNER/cloakbrowser-manager@sha256:DIGEST --apply
```

3. `--apply` waits up to 600 seconds for `running_count == 0`; it never forces an
   active Profile to stop. It saves a private inspect/create manifest and old
   container, starts the replacement and checks health/default selection. Startup
   failure restores the previous container. Secrets remain only in the host's
   private release directory.
4. Test the actual admin and scoped employee ingress, including attempted access
   to another Profile. Run A/B on disposable Profiles. To promote the same image:

```sh
python3 release_viewer.py --image ghcr.io/OWNER/cloakbrowser-manager@sha256:DIGEST \
  --default kasm --acceptance-report /secure/path/qa/report.json --apply
```

5. Keep compatibility available and observe the release for 24 hours: unexpected
   viewer disconnects, native proxy errors, CPU/memory and browser availability.
   The report is evidence, not an authorization to ignore running Profiles.
6. Immediate viewer fallback: select **Compatibility**. Image rollback (waits for
   idle and refuses to overwrite a newer release):

```sh
python3 release_viewer.py --rollback /opt/cloakbrowser-manager/releases/TIMESTAMP --apply
```

Rollback reuses current persistent data; it does not restore an older database,
cookies or Profile directory. Retired containers have restart disabled so a host
reboot cannot accidentally start two Managers against the same data volume.
No Open WebUI, Hermes, Cloudflare ingress or other service restart is required.

Deployment evidence is recorded in [kasmvnc-validation.md](kasmvnc-validation.md).
Outstanding acceptance work is tracked in [kasmvnc-follow-up.md](kasmvnc-follow-up.md).
