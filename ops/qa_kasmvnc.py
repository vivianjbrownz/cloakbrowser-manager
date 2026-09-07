#!/usr/bin/env python3
"""Real-browser A/B acceptance. Creates and removes only its own temporary Profiles.

Run from the Manager checkout with .venv/bin/python. Token file is either a bare
token or an AUTH_TOKEN=... env file; credentials never enter output or screenshots.
"""
import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import statistics
import time
from uuid import uuid4

import httpx
from playwright.async_api import async_playwright


FIXTURE = """<!doctype html><meta charset=utf-8><title>KasmVNC interaction fixture</title>
<style>body{margin:0;background:#eee;height:6000px;font:20px sans-serif}
#marker{position:fixed;left:40px;top:40px;width:120px;height:120px;background:rgb(20,180,80);pointer-events:none}
textarea{position:fixed;left:200px;top:40px;width:450px;height:120px}p{padding-top:200px}
</style><div id=marker></div><textarea id=text aria-label="Test input"></textarea>
<p>Temporary viewer acceptance fixture. Click, type and scroll.</p>
<script>let n=0;window.counts={click:0,keydown:0,wheel:0};
const colors=['rgb(20,180,80)','rgb(200,40,160)','rgb(30,90,220)','rgb(220,160,20)'];
for(const name of Object.keys(counts))document.addEventListener(name,()=>{
 counts[name]++;marker.style.background=colors[++n%colors.length];
});</script>"""

FINGERPRINT = """() => ({userAgent:navigator.userAgent, platform:navigator.platform,
 hardwareConcurrency:navigator.hardwareConcurrency, screen:[screen.width,screen.height,screen.colorDepth],
 viewport:[innerWidth,innerHeight], locale:navigator.language,
 timezone:Intl.DateTimeFormat().resolvedOptions().timeZone})"""

# Samples the decoded canvas, not an HTTP response or server-side DOM change.
ARM_SAMPLE = """({x,y,eventType}) => {
 const canvas=document.querySelector('[data-testid="vnc-canvas-container"] canvas');
 const ctx=canvas.getContext('2d'); const old=ctx.getImageData(x,y,1,1).data;
 window.__viewerSample=new Promise((resolve,reject)=>{
  let start=null,raf;
  const input=()=>{start=performance.now()};
  document.addEventListener(eventType,input,{capture:true,once:true});
  const timeout=setTimeout(()=>{cancelAnimationFrame(raf);document.removeEventListener(eventType,input,true);reject(Error('No painted feedback within 15s'))},15000);
  const poll=()=>{
   const pixel=ctx.getImageData(x,y,1,1).data;
   if(start!==null && Math.abs(pixel[0]-old[0])+Math.abs(pixel[1]-old[1])+Math.abs(pixel[2]-old[2])>100){
    clearTimeout(timeout);document.removeEventListener(eventType,input,true);resolve(performance.now()-start);
   }else raf=requestAnimationFrame(poll);
  };raf=requestAnimationFrame(poll);
 });
}"""


def summarize(samples):
    ordered = sorted(samples)
    return {"samples": len(samples), "median_ms": round(statistics.median(samples), 1),
            "p95_ms": round(ordered[math.ceil(.95 * len(ordered)) - 1], 1),
            "max_ms": round(max(samples), 1)}


async def run(args):
    token = Path(args.token_file).read_text().strip().removeprefix("AUTH_TOKEN=")
    headers = {"Authorization": f"Bearer {token}"}
    report = {"base_url": args.base_url, "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "cases": [], "errors": [], "soak_seconds": args.soak_seconds,
              "note": "Automation host measurements; not a substitute for the user's network/device."}
    async with httpx.AsyncClient(base_url=args.base_url, headers=headers, timeout=90) as api:
        async def request(method, path, **kwargs):
            response = await api.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        report["server"] = await request("GET", "/api/status")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, executable_path=args.chromium or None,
                                             args=["--no-sandbox", "--disable-background-timer-throttling", "--disable-renderer-backgrounding"])
            try:
                for concurrency in args.concurrency:
                    owned, remotes, remote_pages, before = [], [], [], []
                    try:
                        for i in range(concurrency):
                            profile = await request("POST", "/api/profiles", json={
                                "name": f"Kasm QA {uuid4().hex[:8]}", "fingerprint_seed": 456789+i,
                                "screen_width": 1280, "screen_height": 900, "headless": False,
                                "humanize": False, "geoip": False, "restore_last_session": False,
                                "clipboard_sync": False, "notes": "Temporary KasmVNC acceptance Profile",
                            })
                            owned.append(profile)
                            await request("POST", f"/api/profiles/{profile['id']}/launch")
                            endpoint = args.base_url.replace("https:", "wss:").replace("http:", "ws:")
                            remote = await p.chromium.connect_over_cdp(f"{endpoint}/api/profiles/{profile['id']}/cdp", headers=headers)
                            remotes.append(remote)
                            target = remote.contexts[0].pages[0]
                            await target.route("http://127.0.0.1:8080/__viewer_qa", lambda route: route.fulfill(content_type="text/html", body=FIXTURE))
                            await target.goto("http://127.0.0.1:8080/__viewer_qa")
                            await target.evaluate("localStorage.setItem('viewer-qa-session', 'preserved')")
                            remote_pages.append(target)
                            before.append(await target.evaluate(FINGERPRINT))

                        for mode in args.modes:
                            contexts = []
                            pages, errors, wire = [], [], {"sent": 0, "received": 0, "closed": 0}
                            try:
                                for profile in owned:
                                    # Separate contexts/windows avoid hidden-tab rAF throttling
                                    # masquerading as remote-server latency in concurrency runs.
                                    context = await browser.new_context(viewport={"width": 1500, "height": 1100}, permissions=["clipboard-read", "clipboard-write"])
                                    contexts.append(context)
                                    await context.add_cookies([{"name": "auth_token", "value": token, "url": args.base_url}])
                                    await context.add_init_script(f"localStorage.setItem('cloakbrowser.viewer.implementation', {json.dumps(mode)});localStorage.setItem('cloakbrowser.viewer.qualityMode','fast')")
                                    await context.add_init_script("""window.__qaSockets=[];
                                      window.WebSocket=new Proxy(window.WebSocket,{construct(Target,args){
                                        const socket=new Target(...args);window.__qaSockets.push(socket);return socket;
                                      }});""")
                                    page = await context.new_page()
                                    page.on("pageerror", lambda error: errors.append(str(error)))
                                    def socket(ws):
                                        if "/vnc" not in ws.url:
                                            return
                                        ws.on("framesent", lambda data: wire.update(sent=wire["sent"]+len(data)))
                                        ws.on("framereceived", lambda data: wire.update(received=wire["received"]+len(data)))
                                        ws.on("close", lambda: wire.update(closed=wire["closed"]+1))
                                    page.on("websocket", socket)
                                    await page.goto(args.base_url)
                                    await page.get_by_role("button", name=f"Open {profile['name']}", exact=True).first.click()
                                    try:
                                        await page.get_by_text("Connected", exact=True).wait_for(timeout=30000)
                                    except Exception:
                                        print(json.dumps({"connect_errors": errors, "page_text": await page.locator("body").inner_text()}), flush=True)
                                        raise
                                    pages.append(page)

                                async def exercise(page, target, index):
                                    await page.bring_to_front()
                                    canvas = page.locator('[data-testid="vnc-canvas-container"] canvas')
                                    await target.evaluate("() => {text.value='';window.scrollTo(0,0);marker.style.background='rgb(20,180,80)'}")
                                    # Find the marker in actual decoded pixels; no assumptions about
                                    # browser title bars, X decorations or viewport scaling.
                                    marker = await page.wait_for_function("""() => {
                                      const c=document.querySelector('[data-testid="vnc-canvas-container"] canvas');
                                      if(!c||!c.width)return false;
                                      const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
                                      for(let y=8;y<c.height-16;y+=8)for(let x=8;x<200;x+=8){
                                       const i=(y*c.width+x)*4;
                                       if(Math.abs(d[i]-20)<25&&Math.abs(d[i+1]-180)<25&&Math.abs(d[i+2]-80)<25)return {x:x+16,y:y+16};
                                      }return false;
                                    }""", timeout=15000)
                                    point = await marker.json_value()
                                    dims = await canvas.evaluate("c=>({w:c.width,h:c.height})")
                                    box = await canvas.bounding_box()
                                    x, y = box["x"]+point["x"]*box["width"]/dims["w"], box["y"]+point["y"]*box["height"]/dims["h"]
                                    await page.mouse.click(x, y)
                                    # Record XInput's first-wheel initialization separately from
                                    # steady-state samples; do not count it as painted feedback.
                                    first_scroll_before = await target.evaluate("counts.wheel")
                                    await page.mouse.wheel(0, 120)
                                    await page.wait_for_timeout(300)
                                    first_scroll_received = await target.evaluate("counts.wheel") > first_scroll_before
                                    await page.mouse.wheel(0, 120)
                                    await target.locator("#text").focus()
                                    await page.wait_for_timeout(200)
                                    results = {"visibility": await page.evaluate("document.visibilityState")}
                                    for action, event in [("click", "mousedown"), ("typing", "keydown"), ("scroll", "wheel")]:
                                        if action == "typing":
                                            await target.locator("#text").focus()
                                        samples = []
                                        for _ in range(args.samples):
                                            await page.evaluate(ARM_SAMPLE, {**point, "eventType": event})
                                            if action == "click": await page.mouse.click(x, y)
                                            elif action == "typing": await page.keyboard.press("a")
                                            else: await page.mouse.wheel(0, 120)
                                            try:
                                                samples.append(await page.evaluate("window.__viewerSample"))
                                            except Exception:
                                                await page.screenshot(path=str(Path(args.output).parent / f"failure-{mode}-{action}.png"))
                                                print(json.dumps({"failed_action": action, "point": point, "box": box,
                                                    "remote": await target.evaluate("({counts,scrollY,text:text.value,marker:getComputedStyle(marker).backgroundColor})"),
                                                    "client_errors": errors}), flush=True)
                                                raise
                                            await page.wait_for_timeout(50)
                                        results[action] = summarize(samples)
                                    assert await target.locator("#text").input_value() == "a" * args.samples, "Lost or duplicated typing"
                                    assert await target.evaluate("scrollY") > 0, "Scroll did not reach the browser"
                                    after = await target.evaluate(FINGERPRINT)
                                    assert after == before[index], "Viewer changed browser fingerprint/geometry"
                                    results["first_scroll_received"] = first_scroll_received
                                    if index == 0:
                                        out = Path(args.output).parent
                                        await page.screenshot(path=str(out/f"kasm-qa-{concurrency}-{mode}.png"))
                                    return results

                                measurements = await asyncio.gather(*(exercise(page, target, i) for i, (page, target) in enumerate(zip(pages, remote_pages))))
                                functional = {}
                                if mode == "kasm":
                                    page, target = pages[0], remote_pages[0]
                                    await page.bring_to_front()
                                    await page.locator('[data-testid="vnc-canvas-container"] canvas').click(position={"x": 40, "y": 200})
                                    await target.locator("#text").fill("")
                                    await target.locator("#text").focus()
                                    await page.get_by_role("textbox", name="Remote browser keyboard").dispatch_event("compositionstart")
                                    await page.keyboard.insert_text("中文输入测试")
                                    await page.get_by_role("textbox", name="Remote browser keyboard").dispatch_event("compositionend")
                                    await target.wait_for_function("text.value === '中文输入测试'", timeout=5000)
                                    functional["chinese_composition"] = True
                                    await target.locator("#text").fill("")
                                    await page.evaluate("navigator.clipboard.writeText('QA 中文粘贴一次')")
                                    await page.keyboard.press("Control+v")
                                    try:
                                        await target.wait_for_function("text.value === 'QA 中文粘贴一次'", timeout=5000)
                                    except Exception:
                                        print(json.dumps({"paste_remote": await target.locator("#text").input_value(),
                                            "remote_clipboard": await request("GET", f"/api/profiles/{owned[0]['id']}/clipboard"),
                                            "host_clipboard": await page.evaluate("navigator.clipboard.readText()"),
                                            "focus": await page.evaluate("document.activeElement?.outerHTML"), "errors": errors}), flush=True)
                                        raise
                                    functional["paste_once_without_sync"] = True
                                    for label in ["Balanced", "Sharp", "Fast"]:
                                        await page.get_by_role("button", name=label, exact=True).click()
                                    await page.get_by_title("Fullscreen", exact=True).click()
                                    await page.wait_for_function("!!document.fullscreenElement")
                                    await page.evaluate("document.exitFullscreen()")
                                    assert await target.evaluate(FINGERPRINT) == before[0]
                                    assert await target.evaluate("localStorage.getItem('viewer-qa-session')") == "preserved"
                                    functional["quality_fullscreen_session_preserved"] = True
                                    closed_before = wire["closed"]
                                    await page.evaluate("window.__qaSockets.filter(s=>s.url.includes('/vnc-native')&&s.readyState===1).forEach(s=>s.close(1000,'QA reconnect'))")
                                    await page.get_by_text("Reconnecting (1/5)…", exact=True).wait_for()
                                    await page.get_by_text("Connected", exact=True).wait_for(timeout=10000)
                                    assert wire["closed"] == closed_before+1
                                    wire["closed"] -= 1  # Deliberate disconnection, not a stability failure.
                                    assert await target.evaluate(FINGERPRINT) == before[0]
                                    functional["reconnect_without_browser_restart"] = True
                                if mode == "kasm" and args.soak_seconds and concurrency == max(args.concurrency):
                                    deadline = time.monotonic()+args.soak_seconds
                                    while time.monotonic() < deadline:
                                        for page in pages:
                                            await page.keyboard.press("ArrowDown")
                                            assert await page.get_by_text("Connected", exact=True).count() == 1
                                        await asyncio.sleep(min(30, max(0, deadline-time.monotonic())))
                                        print(f"soak concurrency={concurrency}: {max(0, round(deadline-time.monotonic()))}s remaining", flush=True)
                                assert not errors, f"Viewer JavaScript errors: {errors}"
                                assert wire["closed"] == 0, "Unexpected viewer disconnect"
                                report["cases"].append({"concurrency": concurrency, "mode": mode, "measurements": measurements, "wire": wire, "functional": functional, "fingerprint_unchanged": True})
                                print(json.dumps(report["cases"][-1]), flush=True)
                            finally:
                                await asyncio.gather(*(context.close() for context in contexts))
                    finally:
                        for remote in remotes:
                            await remote.close()  # Disconnect CDP; manager stops its own QA Profile below.
                        for profile in owned:
                            await request("POST", f"/api/profiles/{profile['id']}/stop")
                            await request("DELETE", f"/api/profiles/{profile['id']}")
            except Exception as exc:
                report["errors"].append(f"{type(exc).__name__}: {exc}")
                raise
            finally:
                await browser.close()
                Path(args.output).write_text(json.dumps(report, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18981")
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--chromium", default=os.environ.get("QA_CHROMIUM", ""))
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 3])
    parser.add_argument("--modes", nargs="+", choices=["novnc", "kasm"], default=["novnc", "kasm"])
    parser.add_argument("--soak-seconds", type=int, default=0)
    args = parser.parse_args()
    if args.samples < 1 or any(n < 1 or n > 3 for n in args.concurrency):
        parser.error("Use positive sample counts and 1–3 simultaneous QA Profiles")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(run(args))
