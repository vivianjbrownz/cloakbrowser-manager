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

Status: open until the finite observation task finishes.

The deployed observer records health, running/total Profile counts, CPU/memory
and native proxy warnings every five minutes. It does not restart anything or
send messages. The private log location and service name are in the validation
record. Review records with `ok=false`, unexpected availability changes and
native proxy errors; record the final `observation_complete=true` entry.

An idle healthy server is not proof of viewer stability under user traffic.
Keep the real-browser stability result and user-ingress acceptance separate.
