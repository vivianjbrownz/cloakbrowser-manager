# KasmVNC 1.5.0 validation — 2026-09-08

The immutable image passed the version-upgrade gate and is deployed in
production. Health and the post-release native-viewer functional smoke passed.
Compatibility remains the default; saved viewer preferences remain effective.
H.264 stays off. The 24-hour production observer is running, not yet complete.

## Reproducible build

- Application commit: `e1cfe505e2abef9faf4635b31fdedfa901cf7ad7`.
- Published image: `ghcr.io/vivianjbrownz/cloakbrowser-manager@sha256:fd08b668bdb9f2ec80757ac73a14c33fbd929465bc122add74f856e816fd3465`.
- Previous production image: `sha256:00248081377244b290852ea0457221a9e5bcb0d97fe6e4927d6bc885b44d17a5`.
- [CI run](https://github.com/vivianjbrownz/cloakbrowser-manager/actions/runs/34184822614): frontend 86 tests, backend 265 tests and production build passed. The final local backend run, including additional release/acceptance checks, passed 268 tests. Vendor verification covered 54 files; the changed viewer UI had no detector findings.
- Later commits change QA/release tooling, tests and evidence; the measured
  application image remains pinned above. Acceptance containers received no
  copied application files.

The production/runtime comparison found exactly one installed-package change:
`kasmvncserver 1.3.3-1 → 1.5.0-1`. Browser binary, 187 font files, Python packages
and the existing graphics libraries match. The optional video image adds 60
version-locked libraries without upgrading an installed package; it is a
separate test candidate. See the runtime JSON files and [image.json](image.json).

## Version performance and isolation

Three alternating rounds tested one and three viewers, both client modes, and
50 click/typing/scroll samples per Profile. The old baseline is the actual
production image. The client was Chrome 149.0.7827.114 on the shared 4-CPU,
approximately 8-GiB automation host. Browser Profiles used 1280×900 desktops;
the viewer viewport was 1500×1100. Timing measures input to a changed decoded
canvas pixel, excluding target-site network requests. Server/client processes
share this host, so these are controlled lab results, not mainland/VPN latency.

Each cell is old → new P95 in milliseconds: the median across rounds of the
worst Profile P95 in that case. All 12 comparisons satisfy the <=10% regression
gate. Individual outliers remain in the raw samples, including a slow first
round for three native viewers; no rounds were dropped.

| Client / viewers | Click | Typing | Scroll |
| --- | ---: | ---: | ---: |
| Compatibility / 1 | 234.9 → 167.4 | 288.5 → 192.3 | 284.8 → 249.1 |
| KasmVNC / 1 | 162.9 → 144.2 | 172.9 → 162.3 | 217.4 → 201.7 |
| Compatibility / 3 | 308.2 → 221.2 | 296.1 → 172.0 | 716.3 → 350.6 |
| KasmVNC / 3 | 233.8 → 234.9 | 301.0 → 264.1 | 629.5 → 301.4 |

Canvas/WebGL, browser, screen, locale and timezone fingerprints match across
versions and rounds. The three seeds produce three distinct canvas fingerprints.
Chinese composition/text insertion, both clipboard directions, distinct
per-Profile paste payloads, quality/fullscreen, reconnect and mobile scaling
passed. Live CDP targets remained usable through viewer reconnection and mode
changes, with session data and remote geometry preserved.

The first wheel event still sometimes receives no remote page event in both
versions. It is recorded separately from initialized timing samples. These
results do not pass the separate native-default promotion requirement: that
also needs the actual mainland/Singapore VPN ingress, correct first input and
>=50% improvement over Compatibility for every action.

Full raw data, resources and the 30-minute run are in
[upgrade-report.json](upgrade-report.json); the release decision is reproducible
with [upgrade-evaluation.json](upgrade-evaluation.json) and
`ops/kasm_upgrade_acceptance.py`.

## Thirty-minute stability

An isolated container on the production host used the exact candidate image,
an independent data volume, 2 CPUs, 4 GiB RAM and 64 MiB shared memory. Its
headless CloakBrowser 146 client connected over loopback; production user
Profiles were not part of the fixture.

Three viewers completed 1,800 seconds with zero unexpected WebSocket closes
and zero harness errors. Each viewer produced 57 checked input-to-painted-frame
responses, spaced approximately 30 seconds apart. P95 feedback was 649.6,
881.2 and 525.5 ms under this resource cap. This proves intermittent-interaction
stability, not sustained 30-FPS video or the user's network performance. The
isolated test container and its temporary Profiles were removed afterward.

## Optional software H.264

Three rounds compared image and H.264 modes on the same video-capable image.
The last round confirmed 239–247 actual video decode calls per viewer during
measurement and successful image ↔ video switching without losing the browser
session or changing its geometry. Chinese text was readable in the captured
desktop. Functional success did not satisfy the performance gate.

| Viewers | Click P95, image → video | Typing P95 | Scroll P95 |
| --- | ---: | ---: | ---: |
| 1 | 222.7 → 317.2 ms | 292.8 → 552.4 ms | 314.0 → 365.7 ms |
| 3 | 250.2 → 729.3 ms | 491.2 → 546.5 ms | 442.3 → 771.1 ms |

The single-viewer mean container CPU increased about 12.4%; three-viewer CPU
decreased while latency worsened. H.264 remains disabled. These results use the
automation host's decoding/rendering path and do not establish performance on
the user's own GPU-equipped device. See [video-evaluation.json](video-evaluation.json),
[video-rounds.json](video-rounds.json), and [video screenshot](viewer-video-desktop.png).

## Capacity calibration

The shared 4-CPU / approximately 8-GiB local host completed 5 and 10 open browser
Profiles with three streamed viewers and a 60-second soak at each level.
Background tabs updated one text node every five seconds. The 20-Profile step
stopped after launching 17 Profiles because available host memory fell below
the configured 15% / 1.5-GiB reserve. All temporary Profiles were cleaned up.

This validates the light 10-browser workload on that test host. It does not
establish a 17-browser stable limit, 20-browser capacity, or 20 active viewers
on the production host. See [capacity-summary.json](capacity-summary.json) and
the corresponding `capacity-5/10/20.json` reports.

## Release, recovery and remaining observation

An actual isolated release/rollback drill preserved the data volume and restart
policy. Injecting a backup failure restored the original container. Private
backup directories were mode 0700. See [recovery-drill.json](recovery-drill.json).

The first production idle preflight waited 600 seconds and deferred because
one Profile remained active. A later recheck found zero active Profiles, which
allowed the guarded release to proceed. The release preserves the production
mounts, scoped secrets, limits, 64-MiB shared memory and saved viewer choice.
The stopped old container's complete `/data` is backed up privately before the
new container starts.

The complete data backup is approximately 7.1 GiB; the stopped-container copy
took roughly 12 minutes before the replacement started. All 13 original
Profiles remain. Environment/secrets, mounts and checked runtime options match;
the deployment is healthy and reports KasmVNC 1.5.0 with video disabled.

- Private backup/rollback state: `/opt/cloakbrowser-manager/releases/20260908T044233Z`.
- Retained previous container: `cloakbrowser-manager-pre-kasm-20260908T044233Z`.
- Read-only observer: `cloakbrowser-kasm15-observe-20260908.service`.
- Observer log: `/opt/cloakbrowser-manager/releases/20260908T044233Z/observation.jsonl`.
- Host release tools/reports: `/opt/cloakbrowser-manager/ops/kasm15-validation-20260908/`.

The older 1.3.3 observer was stopped after the new observer became active; its
interrupted observation is superseded, not a completed 24-hour 1.3.3 result.
Review the new log for its final `observation_complete=true` entry after 24
hours. See [release-outcome.json](release-outcome.json) (its `at` is the attempt
start), [post-release-runtime.json](post-release-runtime.json) and
[production-smoke.json](production-smoke.json). The production smoke used one
disposable Profile, three samples per action and an SSH tunnel; it is a
functional check, not another performance-acceptance round.

Both public admin/employee domains return a 302 to Cloudflare Access sign-in.
This confirms the protection is still present, not authenticated end-to-end
access. Actual admin/employee sessions and the mainland/Singapore VPN device
remain separate follow-up checks; see [ingress-check.json](ingress-check.json).

The repeatable procedure and user-device login/QA commands are in
[the upgrade runbook](../../kasmvnc-1.5-upgrade.md). Open follow-ups are maintained
in [kasmvnc-follow-up.md](../../kasmvnc-follow-up.md).
