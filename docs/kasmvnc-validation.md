# KasmVNC deployment validation — 2026-09-07

KasmVNC 1.5.0 superseded this release on 2026-09-08. See the
[current validation record](validation/kasm15/README.md) for its successful
deployment, Compatibility default, disabled H.264 and ongoing observation.
The remaining sections record the historical 1.3.3 deployment.

The native KasmVNC client is deployed on the existing Manager server and can be
selected from the viewer toolbar. **Compatibility remains the default.** The
measured performance has not justified changing that default or claiming that
the user's multi-second delay through Cloudflare is resolved.

## Deployed code and runtime

- Application: `5f2cd4353136e7286ff3fd417594865c6fc74c9f` (initial integration
  `d54886f89cf89c98b10ad87bf176fdd72caf37c3`, followed by container resize handling).
- Image: `ghcr.io/vivianjbrownz/cloakbrowser-manager@sha256:00248081377244b290852ea0457221a9e5bcb0d97fe6e4927d6bc885b44d17a5`.
- [Release CI](https://github.com/vivianjbrownz/cloakbrowser-manager/actions/runs/34143473487):
  253 backend tests, 78 frontend tests, production build and 56-file vendor
  integrity verification passed before image publication.
- A subsequent release-tool check added four tests proving that good latency
  cannot override missing/failed functional results: 257 backend tests passed
  locally. This changes the host-side release guard, not the deployed application.
- KasmVNC server remains 1.3.3-1. Official client source remains pinned to
  `bce2d6a7048025c6e6c05df9d98b206c23f6dbab` with the documented Manager patches.

Current, pinned-base and candidate runtime fingerprints matched:

| Component | SHA-256 |
| --- | --- |
| CloakBrowser 146.0.7680.177.5 binary | `715722e8605ae3ce81523c1218aba1ec89425786ab33ceaf99f8a6cb5e70e6e8` |
| 187 font files | `0906d36aab4cdf55f9f79da191af3bb87aaebf003da38e94180a3b51ea329e6c` |
| Python package metadata | `6c9c8fb2833fdda96ab3e1d045a9220dcd23074221f0245dc019964cc42fb9e0` |
| System package versions | `50bee52dcb15a455b6ed333d19da82a1afa1680286069db217201e77565eaa09` |

## Functional and access checks

Real CloakBrowser instances, through the actual React viewer, passed click,
typing and scroll input; Chinese composition; one-time Chinese paste with
continuous sync disabled; remote-to-host text copy with sync enabled; all three
quality presets; fullscreen; and deliberate WebSocket disconnection followed by
automatic reconnection without restarting the browser. The reconnect test
retained the session marker and sampled UA, platform, hardware concurrency,
screen/viewport dimensions, locale and timezone.

Desktop and 390×844 viewport screenshots were inspected. A reproduced upstream
integration issue left the canvas undersized after collapsing the sidebar.
The final patch observes container size changes and cleans up that observer on
disconnect. The real-browser regression check now verifies that the canvas fits
its available area while the remote viewport and sampled fingerprint stay fixed.

Production scoped-identity checks returned only the assigned Profile. Native
connections for another Profile, an untrusted Origin, an anonymous client and a
stopped assigned Profile were rejected before WebSocket upgrade. Both transport
routes also have automated authentication/assignment/Origin coverage. These
server checks do not constitute a successful employee-URL test through Cloudflare.

## Measurement scope and limitations

The production run connects from the automation host through an authenticated
SSH tunnel to the deployed Manager. It measures local input-event to decoded
canvas feedback on a fixed test page, excluding destination website load time.
Each viewer uses a separate browser context, with visible document state checked,
1280×900 remote geometry and the Fast preset. Each action has 50 samples per
Profile at one and three concurrent Profiles.

Initial HEAD requests to the public ingress returned 403. A subsequent ordinary
GET reached Cloudflare Access sign-in on both admin and employee domains. This
is not evidence of a Manager outage: the automation environment lacks an Access
login session. Authenticated public viewers and the user's browser/network
therefore remain unmeasured.
Wire totals include connection setup and extra native functional actions and are
not a normalized bandwidth comparison. An observed frame rate was not captured;
the configured native cap is 30 FPS.

First-wheel initialization is reported separately. The first event has sometimes
produced no feedback with either client on a fresh browser. Steady-state samples
follow two initialization wheel events; they do not prove first-input correctness.
The initial run used Compatibility first, and the final run reverses that order.

The default-promotion gate requires native P95 <=800 ms **and** >=50% improvement
for every action in both concurrency cases, plus successful functional and
30-minute stability checks. A failed performance gate keeps native mode optional.

Final production results, milliseconds; for three Profiles this table shows the
largest per-Profile P95, not a pooled P95:

| Concurrent Profiles | Action | Compatibility P95 | KasmVNC P95 | P95 reduction |
| --- | --- | ---: | ---: | ---: |
| 1 | Click | 498.6 | 671.9 | -34.8% |
| 1 | Typing | 477.0 | 259.9 | +45.5% |
| 1 | Scroll | 581.9 | 350.3 | +39.8% |
| 3 | Click | 385.0 | 436.3 | -13.3% |
| 3 | Typing | 513.0 | 540.6 | -5.4% |
| 3 | Scroll | 603.3 | 625.8 | -3.7% |

All native P95 values are below 800 ms, but the 50% improvement requirement fails.
The guarded default switch rejects this report. Results varied between runs;
they establish neither a consistent speedup nor a precise causal regression.
The reverse-order run received the first wheel event in the second-tested
Compatibility mode, whereas the initial run received it in second-tested native
mode. This supports treating initialization/order as a separate unresolved issue.

Raw data: [final production A/B](validation/production-ab.json),
[initial production A/B](validation/production-ab-initial.json), and
[production resource samples](validation/production-resources.jsonl).
The 35 resource snapshots cover 16:35:22–16:38:50 UTC during the latter part of QA:
peak Docker CPU 625.63% and peak container memory 944.6 MiB on a host reporting
six available logical CPUs. These are aggregate samples across test activity,
not a per-client resource benchmark. The earlier `local-ab.json` remains
preliminary and has explicit environment/concurrency limitations.

## Completed 30-minute connection test

[Native stability report](validation/native-stability.json): three native viewers
on the final application code held their connections for 1,800 seconds, ending
at 16:58:06 UTC. The harness exited successfully at 16:58:09 UTC with zero
unexpected WebSocket closes, no JavaScript errors, all functional assertions
passing and zero QA Profiles remaining after cleanup.

This was an isolated local Manager, checking connection state and sending keyboard
events every 30 seconds. The three input samples per action before the long run
are functional warmup only; use the production report for latency acceptance.
This does not establish stability for continuous heavy-page traffic through the
user's Cloudflare session. An earlier foreground run received SIGTERM and was
excluded; the completed run used an independent finite systemd task.

## Release and recovery

Both release transactions found zero running Profiles before replacing the
Manager. They preserved the 13 existing Profiles, `cloakprofiles:/data`, the
read-only AgentOS configuration mount, authentication environment, loopback
port binding, 64 MiB shared memory and the existing restart/resource policies.
No user Profile was launched or stopped by QA; each test created and removed its
own temporary Profiles.

Latest private rollback state:
`/opt/cloakbrowser-manager/releases/20260907T163230Z`.
Initial integration rollback state:
`/opt/cloakbrowser-manager/releases/20260907T161405Z`.
Retired containers remain stopped with restart disabled. The release script's
apply/rollback flow was also exercised against the isolated QA manager.

Select **Compatibility** for an immediate viewer fallback. The latest image
rollback restores the initial integration image; reverting all the way to the
pre-integration image requires rolling back the latest release first, then the
initial release. Both commands wait for idle Profiles and preserve current data:

```sh
python3 /opt/cloakbrowser-manager/ops/kasmvnc-d54886f/release_viewer.py \
  --rollback /opt/cloakbrowser-manager/releases/20260907T163230Z --apply
python3 /opt/cloakbrowser-manager/ops/kasmvnc-d54886f/release_viewer.py \
  --rollback /opt/cloakbrowser-manager/releases/20260907T161405Z --apply
```

## Post-release observation

The finite, read-only 24-hour observer started on the final deployment at
2026-09-07 16:40 UTC. Its first record was healthy, with zero running and 13 total
Profiles, default `novnc` and zero native proxy warnings. This observation is
ongoing; it has not been represented as a completed 24-hour test.

- Service: `cloakbrowser-kasm-observe-final-20260907.service`.
- Private output: `/opt/cloakbrowser-manager/releases/20260907T163230Z/observation.jsonl`.
- Inspect with `systemctl status` / `journalctl -u` and the private JSONL file.
- The last record will have `observation_complete=true`. No automatic restarts,
  traffic changes or notifications are configured.

Outstanding acceptance work is recorded in [kasmvnc-follow-up.md](kasmvnc-follow-up.md).
