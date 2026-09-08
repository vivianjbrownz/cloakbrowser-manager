# KasmVNC 1.5 upgrade

This release upgrades the display server and its matching browser client from
1.3.3 to 1.5.0. The first production candidate uses JPEG/WebP over the existing
authenticated WebSocket routes, Canvas2D, 30 FPS and fixed remote geometry.
Compatibility remains the default; an existing user's selected viewer remains
selected. No Cloudflare ingress, browser binary, fonts, Python packages or
Profile fingerprint settings change.

## Build and configuration

`ops/kasmvnc-runtime.json` pins the official Debian 13 Trixie amd64 package,
SHA-256 and matching client commit. `Dockerfile` installs only that package on
the existing frozen runtime. `Dockerfile.kasmvnc` builds the runtime-only layer;
`Dockerfile.full` is for a separately validated foundation rebuild.

The actual `Xvnc -version` is exposed as `kasmvnc_version` in `/api/auth/status`
and `/api/status`. A mismatched native client offers refresh/Compatibility
instead of a reconnect loop. Startup waits for an actual RFB greeting. Local
Xvnc binds and WebSocket proxy authentication remain in force.

`CLOAKBROWSER_KASM_VIDEO_ENABLED=false` is the initial setting. A separate
`Dockerfile.kasmvnc-video` candidate adds exactly the packages in
`ops/kasmvnc-video-packages.json`, without upgrading any installed libraries.
Setting the flag to true enables software AVC and the optional Smooth video
selector. The browser must successfully decode an AVC frame before that option
becomes available; missing capability or decode failure returns to image mode.
Video uses 30 FPS and GOP 30; it never resizes or restarts the browser.

## Repeatable acceptance

Use private token files and separate `/data` volumes. Bind each report to the
immutable Docker image actually tested. Do not copy changed app files into a
container used for acceptance. The baseline should be the currently deployed
image, not a newly rebuilt approximation.

```sh
.venv/bin/python ops/qa_kasm_suite.py \
  --token-file /secure/qa/token --output-dir /secure/qa/rounds
.venv/bin/python ops/qa_kasmvnc.py \
  --base-url http://127.0.0.1:18981 --container cloak-kasm15-qa \
  --token-file /secure/qa/token --chromium /usr/bin/google-chrome \
  --concurrency 3 --modes kasm --samples 50 --soak-seconds 1800 \
  --output /secure/qa/stability.json
.venv/bin/python ops/qa_kasm_capacity.py \
  --token-file /secure/qa/token --output-dir /secure/qa/capacity
```

The suite alternates version and mode order over three independent rounds,
with fresh Profiles for each mode, 50 samples per action, and one/three viewers.
It measures local input to decoded canvas change and records raw samples,
wire bytes, timestamps and container CPU/memory. Compare the median across
rounds of each case's worst-Profile P95. Every click, typing and scroll result
must stay within 10% of 1.3.3. Browser, canvas/WebGL, geometry, locale and timezone
fingerprints must match across versions. Chinese composition, bidirectional
clipboard, fullscreen/quality changes, reconnect and mobile canvas resizing
must pass. Three native viewers must remain connected for 30 minutes.

The soak sends an input every 30 seconds to each viewer and requires painted
feedback each time. Distinct per-Profile paste payloads check input and clipboard
isolation. It measures connection stability under intermittent interaction, not
continuous video rendering.
Capacity calibration opens 5, 10 and 20 browser Profiles with only three
streamed viewers. Background tabs update text every five seconds. It stops on
low host memory or CPU saturation for 60 seconds. Results describe this light
workload and this host, not arbitrary websites or 20 simultaneously streamed
desktops.

Video is a separate decision: run the same workload in image and H.264 modes
on the same video-capable candidate. Require click/typing P95 regression <=10%,
scroll P95 improvement >=20%, mean container CPU increase <=10%, and readable
Chinese text. Leave the flag off if any evidence is missing or fails.

```sh
.venv/bin/python ops/qa_kasm_suite.py --comparison video \
  --baseline-url http://127.0.0.1:18983 --candidate-url http://127.0.0.1:18983 \
  --baseline-container cloak-kasm15-video-qa --candidate-container cloak-kasm15-video-qa \
  --token-file /secure/qa/token --output-dir /secure/qa/video
python ops/kasm_video_acceptance.py /secure/qa/video/rounds.json
```

## Actual mainland / Singapore VPN ingress

Run this on the user's own device connected through the usual VPN. Do not put
Cloudflare cookies or Manager credentials into a repository or shared report.

```sh
python ops/prepare_viewer_access.py \
  --base-url https://browser.beginos.org --output /secure/access.json
python ops/qa_kasmvnc.py \
  --base-url https://browser.beginos.org --access-storage-state /secure/access.json \
  --network-label mainland-vpn-singapore --image-id sha256:DEPLOYED_IMAGE_ID \
  --samples 50 --concurrency 1 3 --soak-seconds 1800 \
  --output /secure/user-network.json
```

Install the harness's `httpx` and `playwright` dependencies and its Chromium
browser locally, or supply `--chromium` with a local Chrome path. The first
command opens a local browser for normal Access/Manager login and stores the
session privately. Delete that session file after testing. Obtain the image ID
from the deployment host. Also record the real VPN route, RTT, device and visible
frame smoothness; these cannot be inferred from server-loopback tests.

Run the scoped employee ingress separately with an employee session; verify
its assigned Profile works and an unassigned Profile is denied. The admin
fixture creates temporary Profiles and therefore requires an admin account.

Default promotion remains a separate gate: P95 <=800 ms and >=50% faster than
Compatibility for each action at both concurrency levels, correct first input,
all functional checks and the stability run on this network. First-wheel loss
has been reproduced on fresh instances in both viewer versions; warmed-up
samples cannot establish that this issue is fixed.

## Guarded release and recovery

Combine `rounds.json`, `stability.json`, `runtime_before`, `runtime_after`, and
`baseline_image_id` into an upgrade report. Validate it with:

```sh
python ops/kasm_upgrade_acceptance.py /secure/upgrade.json --image-id sha256:IMAGE_ID
```

Copy `release_viewer.py`, `kasm_upgrade_acceptance.py`,
`verify_runtime_upgrade.py` and the package locks to the Docker host. Pull the
published immutable image and run a read-only preflight before applying:

```sh
python release_viewer.py --image ghcr.io/OWNER/cloakbrowser-manager@sha256:DIGEST \
  --upgrade-report /secure/upgrade.json
python release_viewer.py --image ghcr.io/OWNER/cloakbrowser-manager@sha256:DIGEST \
  --upgrade-report /secure/upgrade.json --apply
```

The release verifies both image identities against the tested report, preserves
actual mounts/secrets/limits/restart policy, and waits at most 600 seconds for
zero active Profiles. It rechecks immediately before stopping. An active
session defers the release. The stopped old container's `/data` is copied into
the private release directory before the replacement starts. Backup/startup
failure restores the old container. Keep that container and backup available.

Use the saved release directory with `--rollback ... --apply` for recovery.
Rollback retains current Profile data; restoring an older database requires a
separate data-recovery decision. After a successful release, start the existing
finite `monitor_viewer.py` observer for 24 hours and review its completion
record. Starting the observer is not completion of the observation period.

Validation results and remaining work are recorded separately from these
procedures in `docs/validation/kasm15/` and `kasmvnc-follow-up.md`.
