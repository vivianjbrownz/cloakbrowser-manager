"""Run on the user's device: save a private Access/Manager login for viewer QA."""
import argparse
import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright


async def run(args):
    os.umask(0o077)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, executable_path=args.chromium or None)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(args.base_url)
        print("Sign in to Cloudflare Access and CloakBrowser Manager in the opened browser.")
        print("After the profile list appears, return here and press Enter. Credentials stay on this device.")
        await asyncio.to_thread(input)
        status = await page.evaluate("fetch('/api/auth/status').then(r=>r.json())")
        if status.get("role") != "admin" or (status.get("auth_required") and not status.get("authenticated")):
            raise RuntimeError("The QA harness requires a signed-in Manager administrator")
        await context.storage_state(path=str(output))
        output.chmod(0o600)
        await browser.close()
    print("Private login state saved. Delete it after completing the QA run; do not upload or commit it.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://browser.beginos.org")
    parser.add_argument("--output", required=True)
    parser.add_argument("--chromium")
    asyncio.run(run(parser.parse_args()))
