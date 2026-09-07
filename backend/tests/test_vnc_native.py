"""Exercise the native transport without a browser/X server or protocol mocks."""
import asyncio
from contextlib import asynccontextmanager
from threading import Event
from types import SimpleNamespace

import pytest
import websockets
from starlette.websockets import WebSocketDisconnect

from backend import main


@pytest.fixture
def native(monkeypatch, app_client):
    state = SimpleNamespace(opened=Event(), closed=Event(), options={}, sent=[])
    monkeypatch.setattr(main, "AUTH_TOKEN", None)
    monkeypatch.setattr(main, "_profile_live_connections", {})
    monkeypatch.setattr(main, "_profile_last_activity", {})
    monkeypatch.setattr(main.browser_mgr, "running", {"assigned": SimpleNamespace(ws_port=6199)})

    @asynccontextmanager
    async def connect(url, **kwargs):
        state.options = {"url": url, **kwargs}
        queue = asyncio.Queue()

        class Upstream:
            async def send(self, data):
                state.sent.append(data)
                if data == b"close-upstream":
                    await queue.put(None)
                elif data == b"fail-upstream":
                    raise OSError("upstream lost")
                else:
                    await queue.put(data)

            def __aiter__(self):
                return self

            async def __anext__(self):
                data = await queue.get()
                if data is None:
                    raise StopAsyncIteration
                return data

        state.opened.set()
        try:
            yield Upstream()
        finally:
            state.closed.set()

    monkeypatch.setattr(websockets, "connect", connect)
    return app_client, state


def test_native_preserves_fragmented_and_batched_binary_messages(native):
    client, state = native
    with client.websocket_connect("/api/profiles/assigned/vnc-native", subprotocols=["binary"]) as ws:
        assert ws.accepted_subprotocol == "binary"
        # RFB handshake fragments, native-only extension types, clipboard, empty
        # frames and concatenated messages must reach the upstream byte-for-byte.
        frames = [b"R", b"FB 003.008\n", b"\x96\x00", b"\xf8\x00\x01\x02",
                  b"\xb4\x00\x00\x00\x04test", b"\x05" + bytes(range(32)), b""]
        for frame in frames:
            ws.send_bytes(frame)
            assert ws.receive_bytes() == frame
        assert state.sent == frames
        assert main._profile_live_connections == {"assigned": 1}
    assert state.closed.wait(2)
    assert not main._profile_live_connections
    assert state.options["url"] == "ws://127.0.0.1:6199/websockify"
    assert state.options["ping_interval"] is None
    assert state.options["compression"] is None
    assert state.options["max_queue"] == 4


@pytest.mark.parametrize("ending,code", [(b"close-upstream", 1000), (b"fail-upstream", 1011)])
def test_native_upstream_exit_closes_client_and_cleans_connections(native, ending, code):
    client, state = native
    with client.websocket_connect("/api/profiles/assigned/vnc-native") as ws:
        assert ws.accepted_subprotocol is None
        ws.send_bytes(ending)
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_bytes()
        assert exc.value.code == code
    assert state.closed.wait(2)
    assert not main._profile_live_connections


def test_native_rejects_text_frames(native):
    client, state = native
    with client.websocket_connect("/api/profiles/assigned/vnc-native") as ws:
        ws.send_text("unexpected")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_bytes()
        assert exc.value.code == 1003
    assert not state.sent
    assert state.closed.wait(2)


def test_native_failed_handshake_cleans_connections(native, monkeypatch):
    client, _ = native

    @asynccontextmanager
    async def fail(*args, **kwargs):
        raise ConnectionRefusedError
        yield  # pragma: no cover

    monkeypatch.setattr(websockets, "connect", fail)
    with client.websocket_connect("/api/profiles/assigned/vnc-native") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_bytes()
        assert exc.value.code == 1011
    assert not main._profile_live_connections


def test_native_stopped_profile_does_not_open_upstream(native):
    client, state = native
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/profiles/missing/vnc-native"):
            pass
    assert exc.value.code == 4004
    assert not state.opened.is_set()
