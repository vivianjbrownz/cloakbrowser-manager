# KasmVNC follow-up records

These records keep the remaining acceptance work in the repository. `bd` is not
installed in the execution environment and this GitHub repository has disabled
Issues. Neither tracking configuration was changed for this release.

## KASM-1: Complete performance acceptance on the user ingress

Status: open. Keep `CLOAKBROWSER_VIEWER_DEFAULT=novnc`.

The production A/B run used an authenticated SSH tunnel to the Manager. It did
not show the required 50% improvement for all actions. Initial HEAD requests to
the public ingress returned 403; ordinary GET requests reached Cloudflare Access
sign-in on both admin and employee domains. The automation environment has no
Access login session, so the user's reported multi-second delay has not been
reproduced or shown to be resolved there.

Acceptance work:

- Measure the actual admin and scoped employee URLs on the user's device and
  network. Record RTT, viewport/device, CPU, memory and observed frame rate.
- Compare both clients on the same fixed page with at least 50 click, typing and
  scroll samples for one and three concurrent Profiles. Alternate mode order.
- Require native P95 <=800 ms and at least 50% improvement for every action,
  with no lost input, cross-Profile input, unexpected disconnect or geometry
  change. Retain compatibility if any gate fails.
- Validate scoped access through the actual employee ingress, including an
  attempted connection to an unassigned Profile. Server-side scope and Origin
  checks already pass; they do not replace ingress verification.
- Only then consider the guarded default-promotion command in the rollout guide.

## KASM-2: Verify first-wheel behavior on fresh browser instances

Status: open. Affects acceptance of the first interaction.

The first wheel event sometimes receives no page feedback in both client modes
on fresh browser instances. Subsequent wheel events work. Reports explicitly
separate this observation from steady-state latency samples. A mode tested
second may benefit from initialization by the first mode.

Reproduce with a fresh browser per mode, trace client/server input and first
paint, and distinguish XInput/browser initialization from an encoding or client
issue. Do not duplicate wheel input as a workaround or change the pinned browser
and fonts as part of this viewer release.

## KASM-3: Review the completed 24-hour observation

Status: superseded by KASM15-1. The 1.3.3 observer was stopped after the 1.5.0
observer became active on 2026-09-08. Its interrupted run must not be described
as a completed 24-hour observation of 1.3.3.

The deployed observer records health, running/total Profile counts, CPU/memory
and native proxy warnings every five minutes. It does not restart anything or
send messages. The private log location and service name are in the validation
record. Review records with `ok=false`, unexpected availability changes and
native proxy errors; record the final `observation_complete=true` entry.

An idle healthy server is not proof of viewer stability under user traffic.
Keep the real-browser stability result and user-ingress acceptance separate.

## KASM15-1: Review the new 24-hour production observation

Status: open; observer started after the successful 1.5.0 release.

Image `sha256:fd08b668bdb9f2ec80757ac73a14c33fbd929465bc122add74f856e816fd3465`
passed three-round version acceptance, fingerprint/isolation checks, a 30-minute
three-viewer soak, and a post-release production smoke. The release waited for
zero active Profiles and retained a complete data backup and old container.
The exact evidence and observer paths are in
[the validation record](validation/kasm15/README.md).

Review the final completion record, availability changes and native proxy
errors. The real mainland/Singapore VPN and authenticated employee ingress
checks in KASM-1 remain open; the Compatibility default remains in effect.

## KASM15-2: Optional H.264 performance

Status: feature implemented and tested; production flag remains off.

The separate software-video candidate passed capability probing, real decoding,
image/video switching, clipboard and session-preservation checks. Three-round
comparisons failed the latency gate on the automation host. Keep it disabled.
Any later evaluation should include the user's actual decoder/GPU and network;
do not generalize these shared-host results to every client device.

## KASM15-3: Capacity above the validated light workload

Status: 5/10-Profile calibration complete; 20-Profile capacity unconfirmed.

The local 4-CPU / approximately 8-GiB host completed the light workload with
three active viewers at 5 and 10 Profiles. The 20 step stopped at 17 launched
Profiles on the memory-reserve guard, then cleaned up every owned Profile.
This is not evidence that 17 are stable or that production can support 20
active websites. Calibrate representative sites on the intended deployment
hardware before increasing operational concurrency.
