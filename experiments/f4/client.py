"""Playlink F4 load client: auth + REST + WebSocket scenario timings."""

from __future__ import annotations

import asyncio
import json
import statistics
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx
import websockets
from eth_account import Account
from eth_account.messages import encode_defunct

Account.enable_unaudited_hdwallet_features()


@dataclass
class Sample:
    scenario: str
    variant: str
    region: str
    ok: bool
    latency_ms: float
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def http_to_ws(url: str) -> str:
    if url.startswith("https://"):
        return "wss://" + url[len("https://") :]
    if url.startswith("http://"):
        return "ws://" + url[len("http://") :]
    return url


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def summarize(samples: list[Sample], scenario: str | None = None) -> dict[str, Any]:
    subset = [s for s in samples if scenario is None or s.scenario == scenario]
    ok = [s for s in subset if s.ok]
    latencies = [s.latency_ms for s in ok]
    errors = [s for s in subset if not s.ok]
    return {
        "n": len(subset),
        "ok": len(ok),
        "errors": len(errors),
        "error_rate": (len(errors) / len(subset)) if subset else None,
        "p50_ms": percentile(latencies, 50),
        "p95_ms": percentile(latencies, 95),
        "mean_ms": statistics.fmean(latencies) if latencies else None,
        "min_ms": min(latencies) if latencies else None,
        "max_ms": max(latencies) if latencies else None,
    }


class RegionClient:
    def __init__(self, region: str, base_url: str, variant: str, timeout: float = 15.0):
        self.region = region
        self.base_url = base_url.rstrip("/")
        self.ws_base = http_to_ws(self.base_url)
        self.variant = variant
        self.timeout = timeout
        # Fresh identity per virtual user (quota: max 3 rooms each).
        self._private = Account.create()
        self.address = self._private.address
        self.token: str | None = None
        self.samples: list[Sample] = []

    def _record(
        self,
        scenario: str,
        ok: bool,
        started: float,
        error: str | None = None,
        **meta: Any,
    ) -> Sample:
        sample = Sample(
            scenario=scenario,
            variant=self.variant,
            region=self.region,
            ok=ok,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            error=error,
            meta=meta,
        )
        self.samples.append(sample)
        return sample

    def login(self) -> None:
        started = time.perf_counter()
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                nonce_resp = client.post(
                    "/auth/request-nonce",
                    params={"address": self.address},
                )
                nonce_resp.raise_for_status()
                nonce = nonce_resp.json()["nonce"]
                message = encode_defunct(text=f"Sign in to Playlink\nNonce: {nonce}")
                signature = self._private.sign_message(message).signature.hex()
                if not signature.startswith("0x"):
                    signature = f"0x{signature}"
                verify = client.post(
                    "/auth/verify",
                    json={
                        "address": self.address,
                        "nonce": nonce,
                        "signature": signature,
                    },
                )
                verify.raise_for_status()
                self.token = verify.json()["token"]
            self._record("auth", True, started)
        except Exception as exc:  # noqa: BLE001
            self._record("auth", False, started, error=str(exc))
            raise

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("not logged in")
        return {"Authorization": f"Bearer {self.token}"}

    def list_rooms(self) -> list[dict[str, Any]]:
        started = time.perf_counter()
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.get("/rooms")
                resp.raise_for_status()
                rooms = resp.json()
            self._record("list_rooms", True, started, count=len(rooms))
            return rooms
        except Exception as exc:  # noqa: BLE001
            self._record("list_rooms", False, started, error=str(exc))
            raise

    def create_room(self, name: str | None = None) -> str:
        room_name = name or f"f4-{self.region}-{uuid.uuid4().hex[:8]}"
        started = time.perf_counter()
        body = {
            "name": room_name,
            "game": "Quake III Arena",
            "lobby_location": "eu-central" if self.region == "eu" else "na-east",
            "players_max": 8,
            "description": f"F4 experiment room ({self.variant}/{self.region})",
        }
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.post("/rooms", json=body, headers=self._headers())
                if resp.status_code == 429:
                    raise RuntimeError("rate_limited")
                resp.raise_for_status()
            self._record("create_room", True, started, room=room_name)
            return room_name
        except Exception as exc:  # noqa: BLE001
            self._record("create_room", False, started, error=str(exc), room=room_name)
            raise

    def join_room(self, room_name: str) -> None:
        started = time.perf_counter()
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.post(
                    f"/rooms/{room_name}/join",
                    headers=self._headers(),
                )
                if resp.status_code == 429:
                    raise RuntimeError("rate_limited")
                # Already a member is fine for repeated iterations.
                if resp.status_code not in (200, 400):
                    resp.raise_for_status()
            self._record("join_room", True, started, room=room_name)
        except Exception as exc:  # noqa: BLE001
            self._record("join_room", False, started, error=str(exc), room=room_name)
            raise

    def leave_room(self, room_name: str) -> None:
        started = time.perf_counter()
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.post(
                    f"/rooms/{room_name}/leave",
                    headers=self._headers(),
                )
                if resp.status_code == 429:
                    raise RuntimeError("rate_limited")
                if resp.status_code not in (200, 400):
                    resp.raise_for_status()
            self._record("leave_room", True, started, room=room_name)
        except Exception as exc:  # noqa: BLE001
            self._record("leave_room", False, started, error=str(exc), room=room_name)
            raise

    async def chat_roundtrip(self, room_name: str) -> None:
        """Join chat WS, send one message, wait until we see our own broadcast."""
        assert self.token
        started = time.perf_counter()
        qs = urlencode({"token": self.token})
        uri = f"{self.ws_base}/ws/rooms/{room_name}/chat?{qs}"
        marker = f"f4-ping-{uuid.uuid4().hex[:10]}"
        try:
            async with websockets.connect(uri, open_timeout=self.timeout) as ws:
                # Drain history frame.
                _ = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                await ws.send(json.dumps({"content": marker}))
                deadline = time.perf_counter() + self.timeout
                while time.perf_counter() < deadline:
                    raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                    payload = json.loads(raw)
                    if payload.get("type") != "message":
                        continue
                    msg = payload.get("message") or {}
                    if msg.get("content") == marker:
                        self._record(
                            "chat_roundtrip",
                            True,
                            started,
                            room=room_name,
                        )
                        return
            self._record(
                "chat_roundtrip",
                False,
                started,
                error="broadcast_timeout",
                room=room_name,
            )
        except Exception as exc:  # noqa: BLE001
            self._record("chat_roundtrip", False, started, error=str(exc), room=room_name)

    async def measure_rooms_ws_update(self, actor: RegionClient) -> None:
        """Observer on /ws/rooms; actor creates a room; measure push latency."""
        started = time.perf_counter()
        uri = f"{self.ws_base}/ws/rooms"
        room_name = f"f4-ws-{self.region}-{uuid.uuid4().hex[:8]}"
        try:
            async with websockets.connect(uri, open_timeout=self.timeout) as ws:
                # Initial snapshot.
                _ = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                create_started = time.perf_counter()
                actor.create_room(room_name)
                deadline = time.perf_counter() + self.timeout
                while time.perf_counter() < deadline:
                    raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                    # Payload is the rooms list JSON (array or object with rooms).
                    if room_name in raw:
                        self._record(
                            "rooms_ws_update",
                            True,
                            create_started,
                            room=room_name,
                            observer_region=self.region,
                            actor_region=actor.region,
                        )
                        return
            self._record(
                "rooms_ws_update",
                False,
                create_started,
                error="ws_update_timeout",
                room=room_name,
            )
        except Exception as exc:  # noqa: BLE001
            self._record(
                "rooms_ws_update",
                False,
                started,
                error=str(exc),
                room=room_name,
            )


async def run_user_flow(
    client: RegionClient,
    *,
    iterations: int,
    pace_s: float,
) -> None:
    """One virtual user: list → create → (joiner joins) → chat → leave."""
    client.login()
    await asyncio.sleep(pace_s)

    for _ in range(iterations):
        client.list_rooms()
        await asyncio.sleep(pace_s)

        room = client.create_room()
        await asyncio.sleep(pace_s)

        # Separate identity joins the room (covers join_room metric).
        joiner = RegionClient(
            region=client.region,
            base_url=client.base_url,
            variant=client.variant,
        )
        try:
            joiner.login()
            await asyncio.sleep(pace_s)
            joiner.join_room(room)
            client.samples.extend(joiner.samples)
        except Exception:  # noqa: BLE001
            client.samples.extend(joiner.samples)

        await client.chat_roundtrip(room)
        await asyncio.sleep(pace_s)

        client.leave_room(room)
        await asyncio.sleep(pace_s)
