"""Shared slowapi rate limiter.

Defined in its own module so every router can apply ``@limiter.limit(...)``
against the same instance that ``main`` registers on ``app.state.limiter``.

The backend sits behind Cloudflare Tunnel, so the direct ASGI peer is the
connector (or the SvelteKit container for SSR calls), never the player. We key
on ``CF-Connecting-IP`` only when the peer is an explicitly trusted proxy;
otherwise the peer address is used. ``X-Forwarded-For`` is deliberately not
trusted because cloudflared appends to it and its leading entries are
attacker-controlled.
"""

import ipaddress
import logging
import os

from fastapi import Request
from slowapi import Limiter

logger = logging.getLogger(__name__)


def _normalize_ip(value: str | None) -> str | None:
    """Return a canonical bare IP string, or None for malformed input."""
    if not value:
        return None
    try:
        parsed = ipaddress.ip_address(value.strip())
    except ValueError:
        return None

    # Normalize IPv4-mapped IPv6 (e.g. ::ffff:172.18.0.2) to plain IPv4 so
    # trust checks against TRUSTED_PROXY_HOSTS behave as expected.
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
        return str(parsed.ipv4_mapped)
    return str(parsed)


def _parse_trusted_proxies(raw: str | None) -> tuple[ipaddress._BaseNetwork, ...]:
    """Parse comma-separated IPs or CIDR ranges (e.g. ``172.16.0.0/12``)."""
    networks: list[ipaddress._BaseNetwork] = []
    for part in (raw or "").split(","):
        if not part.strip():
            continue
        try:
            networks.append(ipaddress.ip_network(part.strip(), strict=False))
        except ValueError:
            logger.warning(
                "Ignoring invalid TRUSTED_PROXY_HOSTS entry: %r", part.strip()
            )
    return tuple(networks)


# Loopback by default. Container deployments trust the private Docker ranges:
# the backend publishes no port there, so only cloudflared and the frontend
# container can reach it.
TRUSTED_PROXIES = _parse_trusted_proxies(
    os.getenv("TRUSTED_PROXY_HOSTS", "127.0.0.1,::1")
)

logger.info("Rate-limit trusted proxies: %s", [str(net) for net in TRUSTED_PROXIES])


def _is_trusted(ip: str) -> bool:
    address = ipaddress.ip_address(ip)
    return any(address in network for network in TRUSTED_PROXIES)


def client_ip_key(request: Request) -> str:
    """Resolve the real client IP for rate limiting."""
    peer = _normalize_ip(request.client.host if request.client else None)
    if peer is None:
        return "unknown"

    if _is_trusted(peer):
        # Only a bare IP literal is accepted; reject lists, ports and hostnames.
        forwarded = _normalize_ip(request.headers.get("cf-connecting-ip"))
        if forwarded:
            return forwarded

    return peer


limiter = Limiter(key_func=client_ip_key)
