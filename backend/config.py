"""Application configuration and module-level constants.

Centralizes environment parsing and the static lookup tables that used to live
at the top of ``main.py``. The ``.env`` at the project root is loaded here (and
also, independently, by ``database.py``) so importing this module is enough to
have settings available.
"""

import os
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root if it exists.
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# --- Auth / JWT ---
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
NONCE_EXPIRATION_MINUTES = int(os.getenv("NONCE_EXPIRATION_MINUTES", "5"))
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))

# --- Background cleanup ---
ROOM_CLEANUP_INTERVAL_SECONDS = int(os.getenv("ROOM_CLEANUP_INTERVAL_SECONDS", "60"))

# --- HTTP rate limiting ---
DEFAULT_RATE_LIMIT = os.getenv("DEFAULT_RATE_LIMIT", "10/minute")

# --- WebSocket chat rate limiting (per-identity sliding window) ---
WS_LIMITS: defaultdict[str, list[float]] = defaultdict(list)
MAX_MSGS = int(os.getenv("WS_RATE_LIMIT_MAX_MESSAGES", "10"))
WINDOW = int(os.getenv("WS_RATE_LIMIT_TIME_WINDOW_SECONDS", "10"))


def _parse_admin_addresses(raw: str | None) -> set[str]:
    """Parse the comma-separated `ADMIN_ADDRESSES` env value into a set.

    Addresses are lower-cased so membership checks are case-insensitive and
    independent of EIP-55 checksum casing. An empty/unset value yields an
    empty set — i.e. the system simply has no admins.
    """
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


# Whitelisted admin identity addresses. Authority lives entirely in the
# environment — there is no `is_admin` column, so the only way to grant power
# is to edit `.env`. Kept mutable at module scope so tests can adjust it.
ADMIN_ADDRESSES: set[str] = _parse_admin_addresses(os.getenv("ADMIN_ADDRESSES"))


def is_admin_address(address: str) -> bool:
    """Return whether `address` is whitelisted as an administrator."""
    return address.lower() in ADMIN_ADDRESSES


# --- Lobby locations ---
LOBBY_LOCATIONS: list[dict[str, str | float]] = [
    {"code": "na-east", "label": "North America East", "lat": 39.0, "lon": -77.0},
    {"code": "na-west", "label": "North America West", "lat": 37.8, "lon": -122.4},
    {"code": "eu-west", "label": "Europe West", "lat": 51.5, "lon": -0.1},
    {"code": "eu-central", "label": "Europe Central", "lat": 50.1, "lon": 8.7},
    {"code": "eu-north", "label": "Europe North", "lat": 59.3, "lon": 18.1},
    {"code": "sa-east", "label": "South America East", "lat": -23.6, "lon": -46.6},
    {"code": "asia-east", "label": "Asia East", "lat": 35.7, "lon": 139.7},
    {"code": "asia-south", "label": "Asia South", "lat": 1.3, "lon": 103.8},
    {"code": "oceania", "label": "Oceania", "lat": -33.9, "lon": 151.2},
    {"code": "africa-south", "label": "Africa South", "lat": -26.2, "lon": 28.0},
]
LOBBY_LOCATION_CODES = {str(location["code"]) for location in LOBBY_LOCATIONS}

# --- Chat ---
SYSTEM_SENDER_ADDRESS = "__system__"

# Issue #59: chat messages are signed with the sender's BIP39-derived key
# (EIP-191 personal_sign) so authorship is verifiable end-to-end rather than
# trusted on the JWT alone. Reject timestamps drifting more than this from the
# server clock to blunt replay of captured signatures.
CHAT_SIGNATURE_SKEW_SECONDS = 120

# --- Games ---
DEFAULT_GAMES: list[str] = [
    "Quake III Arena",
    "Diablo II",
    "StarCraft",
    "Half-Life",
    "Unreal Tournament",
]
