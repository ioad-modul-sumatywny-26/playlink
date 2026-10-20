#!/usr/bin/env python3
"""Seed a local Playlink instance with a demo user and sample rooms.

Idempotent: if any rooms already exist, nothing is created or deleted.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from eth_account import Account
from eth_account.messages import encode_defunct

BASE_URL = os.environ.get("PLAYLINK_BASE_URL", "http://localhost:8000").rstrip("/")
DEMO_MNEMONIC = "test test test test test test test test test test test junk"
DEMO_USERNAME = "demo_host"

SEED_ROOMS = [
    {
        "name": "q3-fragfest",
        "game": "Quake III Arena",
        "lobby_location": "eu-central",
        "players_max": 8,
        "description": "Casual CPMA fragfest - local demo lobby",
        "requirements": "CPMA mod recommended",
    },
    {
        "name": "d2-baal-runs",
        "game": "Diablo II",
        "lobby_location": "eu-west",
        "players_max": 4,
        "description": "Ladder Baal runs, softcore",
        "requirements": "Ladder characters only",
    },
    {
        "name": "sc-broodwar",
        "game": "StarCraft",
        "lobby_location": "na-east",
        "players_max": 2,
        "description": "1v1 Brood War practice",
        "requirements": "Latest 1.16.1 patch",
    },
]


def _request(
    method: str,
    path: str,
    *,
    data: dict | None = None,
    token: str | None = None,
    params: dict[str, str] | None = None,
) -> tuple[int, object]:
    url = f"{BASE_URL}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    body = None
    headers = {"Accept": "application/json"}
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else None
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw) if raw else {"detail": raw}
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return exc.code, payload


def _login(account: Account) -> str:
    status, payload = _request(
        "POST",
        "/auth/request-nonce",
        params={"address": account.address},
    )
    if status != 200 or not isinstance(payload, dict) or "nonce" not in payload:
        raise RuntimeError(f"request-nonce failed ({status}): {payload}")

    nonce = payload["nonce"]
    message = encode_defunct(text=f"Sign in to Playlink\nNonce: {nonce}")
    signature = account.sign_message(message).signature.hex()
    if not signature.startswith("0x"):
        signature = f"0x{signature}"

    status, payload = _request(
        "POST",
        "/auth/verify",
        data={
            "address": account.address,
            "nonce": nonce,
            "signature": signature,
        },
    )
    if status != 200 or not isinstance(payload, dict) or "token" not in payload:
        raise RuntimeError(f"verify failed ({status}): {payload}")
    return payload["token"]


def _ensure_username(token: str) -> str:
    status, me = _request("GET", "/users/me", token=token)
    if status != 200 or not isinstance(me, dict):
        raise RuntimeError(f"/users/me failed ({status}): {me}")

    current = me.get("username", "")
    if current == DEMO_USERNAME:
        return current

    status, updated = _request(
        "PATCH",
        "/users/me",
        data={"username": DEMO_USERNAME},
        token=token,
    )
    if status == 200 and isinstance(updated, dict):
        return updated.get("username", DEMO_USERNAME)
    # Username may already be taken by a previous seed — keep whatever we have.
    print(f"  username left as '{current}' (could not set '{DEMO_USERNAME}': {updated})")
    return current


def main() -> int:
    Account.enable_unaudited_hdwallet_features()
    account = Account.from_mnemonic(DEMO_MNEMONIC)

    print(f"Playlink local seed -> {BASE_URL}")
    print(f"  demo address : {account.address}")
    print(f"  demo mnemonic: {DEMO_MNEMONIC}")

    status, rooms = _request("GET", "/rooms")
    if status != 200:
        print(f"ERROR: GET /rooms failed ({status}): {rooms}", file=sys.stderr)
        return 1

    if isinstance(rooms, list) and len(rooms) > 0:
        print(f"  rooms already present ({len(rooms)}) - skipping seed (no wipe)")
        for room in rooms:
            if isinstance(room, dict):
                print(f"    - {room.get('name')} [{room.get('game')}]")
        return 0

    print("  no rooms found - creating demo user + lobbies")
    token = _login(account)
    username = _ensure_username(token)
    print(f"  user ready   : {username} ({account.address})")

    created = 0
    for body in SEED_ROOMS:
        status, payload = _request("POST", "/rooms", data=body, token=token)
        if status == 201:
            created += 1
            print(f"  created room : {body['name']}")
        elif status == 409:
            print(f"  room exists  : {body['name']}")
        else:
            print(f"  FAILED room  : {body['name']} ({status}) {payload}", file=sys.stderr)

    status, rooms = _request("GET", "/rooms")
    count = len(rooms) if isinstance(rooms, list) else "?"
    print(f"  done - active rooms: {count}")
    print("  open http://localhost:3000/rooms")
    print("  to log in as demo host, paste the mnemonic on the IDENTITY page")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
