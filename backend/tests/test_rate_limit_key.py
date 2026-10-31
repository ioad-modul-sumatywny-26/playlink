"""Unit tests for the Cloudflare-aware rate-limit key."""

from starlette.requests import Request

from rate_limit import client_ip_key


def make_request(peer: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
    ]
    return Request({"type": "http", "client": (peer, 12345), "headers": raw_headers})


def test_trusted_peer_uses_cf_connecting_ip():
    request = make_request("127.0.0.1", {"cf-connecting-ip": "203.0.113.7"})
    assert client_ip_key(request) == "203.0.113.7"


def test_untrusted_peer_ignores_cf_connecting_ip():
    request = make_request("10.1.2.3", {"cf-connecting-ip": "203.0.113.7"})
    assert client_ip_key(request) == "10.1.2.3"


def test_missing_header_falls_back_to_peer():
    assert client_ip_key(make_request("127.0.0.1")) == "127.0.0.1"


def test_malformed_header_falls_back_to_peer():
    request = make_request("127.0.0.1", {"cf-connecting-ip": "203.0.113.7, 10.0.0.1"})
    assert client_ip_key(request) == "127.0.0.1"

    request = make_request("127.0.0.1", {"cf-connecting-ip": "not-an-ip"})
    assert client_ip_key(request) == "127.0.0.1"


def test_ipv4_mapped_ipv6_is_normalized():
    request = make_request(
        "::ffff:127.0.0.1", {"cf-connecting-ip": "::ffff:203.0.113.7"}
    )
    assert client_ip_key(request) == "203.0.113.7"


def test_trusted_proxy_cidr(monkeypatch):
    import rate_limit

    monkeypatch.setattr(
        rate_limit,
        "TRUSTED_PROXIES",
        rate_limit._parse_trusted_proxies("172.16.0.0/12"),
    )
    request = make_request("172.20.0.5", {"cf-connecting-ip": "203.0.113.7"})
    assert client_ip_key(request) == "203.0.113.7"
    request = make_request("192.168.1.5", {"cf-connecting-ip": "203.0.113.7"})
    assert client_ip_key(request) == "192.168.1.5"
