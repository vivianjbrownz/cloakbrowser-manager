"""KasmVNC display allocation and lifecycle management."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache

import websockets

logger = logging.getLogger("cloakbrowser.manager.vnc")


@lru_cache(maxsize=1)
def kasmvnc_version() -> str | None:
    """Read the installed server, not a build label or caller-controlled value."""
    try:
        result = subprocess.run(["Xvnc", "-version"], capture_output=True, text=True, timeout=3)
        match = re.search(r"Xvnc KasmVNC (\d+\.\d+\.\d+)", result.stdout + result.stderr)
        return match[1] if match else None
    except (OSError, subprocess.TimeoutExpired):
        return None


@dataclass
class VNCInstance:
    display: int
    ws_port: int
    process: subprocess.Popen | None = None


class VNCManager:
    BASE_DISPLAY = 100
    BASE_WS_PORT = 6100

    def __init__(self):
        self._allocated: dict[int, VNCInstance] = {}
        self._lock = asyncio.Lock()

    async def allocate(self) -> tuple[int, int]:
        """Returns (display_number, ws_port) for a new profile."""
        async with self._lock:
            display = self.BASE_DISPLAY
            while display in self._allocated:
                display += 1
            ws_port = self.BASE_WS_PORT + (display - self.BASE_DISPLAY)
            self._allocated[display] = VNCInstance(display=display, ws_port=ws_port)
            return display, ws_port

    async def start_vnc(
        self,
        display: int,
        ws_port: int,
        width: int = 1920,
        height: int = 1080,
    ) -> subprocess.Popen:
        """Start Xvnc (KasmVNC) on the given display."""
        xvnc_bin = shutil.which("Xvnc") or "Xvnc"

        # KasmVNC requires -httpd to enable the WebSocket handler on the websocket port.
        # Without it, the port accepts TCP but won't do WebSocket upgrade.
        httpd_dir = "/usr/share/kasmvnc/www"

        cmd = [
            xvnc_bin,
            f":{display}",
            "-websocketPort", str(ws_port),
            "-rfbport", "-1",  # disable raw VNC TCP port — WebSocket only
            "-geometry", f"{width}x{height}",
            "-depth", "24",
            "-SecurityTypes", "None",
            "-DisableBasicAuth",
            "-interface", "127.0.0.1",  # internal only, proxied by FastAPI
            "-PublicIP", "127.0.0.1",  # WebSocket-only; skip automatic STUN IP discovery
            "-AlwaysShared",
            "-httpd", httpd_dir,
        ]
        if os.environ.get("CLOAKBROWSER_KASM_VIDEO_ENABLED", "false").lower() in {"true", "1"}:
            # Direct Xvnc invocation does not load vncserver's YAML defaults.
            # Probe only software AVC; enabling the UI never selects a GPU.
            cmd.extend(["-videoCodec", "h264"])

        log_path = f"/tmp/xvnc-{display}.log"
        logger.info("Starting Xvnc on :%d (ws_port=%d) log=%s", display, ws_port, log_path)

        log_file = open(log_path, "w")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
        )
        log_file.close()  # Popen inherited the fd, parent doesn't need it

        async def ready():
            while proc.poll() is None:
                try:
                    async with websockets.connect(
                        f"ws://127.0.0.1:{ws_port}/websockify", subprotocols=["binary"],
                        origin=f"http://127.0.0.1:{ws_port}",
                        compression=None, open_timeout=1, close_timeout=0.2,
                    ) as socket:
                        greeting = await asyncio.wait_for(socket.recv(), 1)
                        if isinstance(greeting, bytes) and greeting.startswith(b"RFB "):
                            return
                except (OSError, TimeoutError, websockets.WebSocketException):
                    pass
                await asyncio.sleep(0.1)
            raise RuntimeError("Xvnc exited before readiness")

        try:
            await asyncio.wait_for(ready(), timeout=10)
        except BaseException as exc:
            if proc.poll() is None:
                proc.terminate()
                try:
                    await asyncio.to_thread(proc.wait, 3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    await asyncio.to_thread(proc.wait)
            async with self._lock:
                self._allocated.pop(display, None)
            if isinstance(exc, asyncio.CancelledError):
                raise
            try:
                with open(log_path) as f:
                    err = f.read()[-4000:]
            except OSError:
                err = ""
            raise RuntimeError(f"Xvnc failed readiness on :{display}: {err}") from exc

        async with self._lock:
            if display in self._allocated:
                self._allocated[display].process = proc

        return proc

    async def stop_vnc(self, display: int):
        """Kill Xvnc for given display and release allocation."""
        async with self._lock:
            instance = self._allocated.pop(display, None)

        if instance and instance.process:
            logger.info("Stopping Xvnc on :%d", display)
            instance.process.terminate()
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, instance.process.wait, 5,
                )
            except subprocess.TimeoutExpired:
                instance.process.kill()

    async def cleanup_all(self):
        """Kill all managed Xvnc processes. Called on shutdown."""
        async with self._lock:
            displays = list(self._allocated.keys())

        for display in displays:
            await self.stop_vnc(display)

    async def cleanup_stale(self):
        """Kill orphan Xvnc processes from previous runs."""
        try:
            result = subprocess.run(
                ["pkill", "-f", r"Xvnc :[0-9]"],
                capture_output=True,
            )
            if result.returncode == 0:
                logger.info("Cleaned up stale Xvnc processes")
        except FileNotFoundError:
            logger.debug("pkill not found, skipping stale Xvnc cleanup")

    def get_ws_port(self, display: int) -> int | None:
        """Get WebSocket port for a display."""
        instance = self._allocated.get(display)
        return instance.ws_port if instance else None

    @property
    def active_displays(self) -> list[int]:
        return list(self._allocated.keys())
