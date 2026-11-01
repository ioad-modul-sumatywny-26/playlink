"""Playlink F4 load client: auth + REST + WebSocket scenario timings.

Uses httpx.AsyncClient so virtual users under asyncio.gather actually overlap.
HTTP/WS failures (including 429) are recorded and do not abort the run.
"""

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


def _http_error(resp: httpx.Response) -> str:
    if resp.status_code == 429:
        return "rate_limited"
    detail = ""
    try:
        payload = resp.json()
        if isinstance(payload, dict) and payload.get("detail") is not None:
            detail = f": {payload['detail']}"
    except Exception:  # noqa: BLE001
        detail = ""
    return f"HTTP {resp.status_code}{detail}"


class RegionClient:
    """One virtual user against a single regional API."""

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
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> RegionClient:
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("RegionClient must be used as 'async with'")
        return self._http

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

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("not logged in")
        return {"Authorization": f"Bearer {self.token}"}

    async def login(self) -> bool:
        started = time.perf_counter()
        try:
            nonce_resp = await self.http.post(
                "/auth/request-nonce",
                params={"address": self.address},
            )
            if nonce_resp.status_code != 200:
                self._record("auth", False, started, error=_http_error(nonce_resp))
                return False
            nonce = nonce_resp.json()["nonce"]
            message = encode_defunct(text=f"Sign in to Playlink\nNonce: {nonce}")
            signature = self._private.sign_message(message).signature.hex()
            if not signature.startswith("0x"):
                signature = f"0x{signature}"
            verify = await self.http.post(
                "/auth/verify",
                json={
                    "address": self.address,
                    "nonce": nonce,
                    "signature": signature,
                },
            )
            if verify.status_code != 200:
                self._record("auth", False, started, error=_http_error(verify))
                return False
            self.token = verify.json()["token"]
            self._record("auth", True, started)
            return True
        except Exception as exc:  # noqa: BLE001
            self._record("auth", False, started, error=str(exc))
            return False

    async def list_rooms(self) -> list[dict[str, Any]]:
        started = time.perf_counter()
        try:
            resp = await self.http.get("/rooms")
            if resp.status_code != 200:
                self._record("list_rooms", False, started, error=_http_error(resp))
                return []
            rooms = resp.json()
            if not isinstance(rooms, list):
                self._record("list_rooms", False, started, error="unexpected_payload")
                return []
            self._record("list_rooms", True, started, count=len(rooms))
            return rooms
        except Exception as exc:  # noqa: BLE001
            self._record("list_rooms", False, started, error=str(exc))
            return []

    async def create_room(self, name: str | None = None) -> str | None:
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
            resp = await self.http.post("/rooms", json=body, headers=self._headers())
            if resp.status_code == 429:
                self._record(
                    "create_room", False, started, error="rate_limited", room=room_name
                )
                return None
            if resp.status_code not in (200, 201):
                self._record(
                    "create_room",
                    False,
                    started,
                    error=_http_error(resp),
                    room=room_name,
                )
                return None
            self._record("create_room", True, started, room=room_name)
            return room_name
        except Exception as exc:  # noqa: BLE001
            self._record(
                "create_room", False, started, error=str(exc), room=room_name
            )
            return None

    async def join_room(self, room_name: str) -> bool:
        started = time.perf_counter()
        try:
            resp = await self.http.post(
                f"/rooms/{room_name}/join",
                headers=self._headers(),
            )
            if resp.status_code == 429:
                self._record(
                    "join_room", False, started, error="rate_limited", room=room_name
                )
                return False
            # Already a member is fine for repeated iterations.
            if resp.status_code not in (200, 400):
                self._record(
                    "join_room",
                    False,
                    started,
                    error=_http_error(resp),
                    room=room_name,
                )
                return False
            self._record("join_room", True, started, room=room_name)
            return True
        except Exception as exc:  # noqa: BLE001
            self._record("join_room", False, started, error=str(exc), room=room_name)
            return False

    async def leave_room(self, room_name: str) -> bool:
        started = time.perf_counter()
        try:
            resp = await self.http.post(
                f"/rooms/{room_name}/leave",
                headers=self._headers(),
            )
            if resp.status_code == 429:
                self._record(
                    "leave_room", False, started, error="rate_limited", room=room_name
                )
                return False
            if resp.status_code not in (200, 400):
                self._record(
                    "leave_room",
                    False,
                    started,
                    error=_http_error(resp),
                    room=room_name,
                )
                return False
            self._record("leave_room", True, started, room=room_name)
            return True
        except Exception as exc:  # noqa: BLE001
            self._record("leave_room", False, started, error=str(exc), room=room_name)
            return False

    async def chat_roundtrip(self, room_name: str) -> None:
        """Join chat WS, send one message, wait until we see our own broadcast."""
        if not self.token:
            self._record(
                "chat_roundtrip",
                False,
                time.perf_counter(),
                error="not_logged_in",
                room=room_name,
            )
            return
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
            self._record(
                "chat_roundtrip", False, started, error=str(exc), room=room_name
            )

    async def measure_rooms_ws_update(self, actor: RegionClient) -> None:
        """Observer on /ws/rooms; actor creates a room; measure push latency."""
        started = time.perf_counter()
        uri = f"{self.ws_base}/ws/rooms"
        room_name = f"f4-ws-{self.region}-{uuid.uuid4().hex[:8]}"
        create_started = started
        try:
            async with websockets.connect(uri, open_timeout=self.timeout) as ws:
                # Initial snapshot.
                _ = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                create_started = time.perf_counter()
                created = await actor.create_room(room_name)
                if created is None:
                    # create_room already recorded its own sample; mark WS probe too.
                    self._record(
                        "rooms_ws_update",
                        False,
                        create_started,
                        error="create_failed",
                        room=room_name,
                    )
                    return
                deadline = time.perf_counter() + self.timeout
                while time.perf_counter() < deadline:
                    raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
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
    """One virtual user: list → create → (joiner joins) → chat → leave.

    Never raises: every failure is a sample so the report error rate is honest.
    """
    async with client:
        if not await client.login():
            return
        await asyncio.sleep(pace_s)

        for _ in range(iterations):
            await client.list_rooms()
            await asyncio.sleep(pace_s)

            room = await client.create_room()
            if room is None:
                await asyncio.sleep(pace_s)
                continue
            await asyncio.sleep(pace_s)

            # Separate identity joins the room (covers join_room metric).
            joiner = RegionClient(
                region=client.region,
                base_url=client.base_url,
                variant=client.variant,
            )
            async with joiner:
                if await joiner.login():
                    await asyncio.sleep(pace_s)
                    await joiner.join_room(room)
            client.samples.extend(joiner.samples)

            await client.chat_roundtrip(room)
            await asyncio.sleep(pace_s)

            await client.leave_room(room)
            await asyncio.sleep(pace_s)
