"""SSRF defenses: validate alert webhook / RTSP URLs before issuing requests.

Why: alert channels and the /probe endpoint accept user-controlled URLs from the
DSL or HTTP body. Without validation a hostile config could point them at
169.254.169.254 (cloud metadata), 127.0.0.1, file://, or arbitrary internal hosts.
We enforce scheme allow-lists and block private/loopback/link-local addresses.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

WEBHOOK_SCHEMES = ("https",)
RTSP_SCHEMES = ("rtsp", "rtsps")


class UnsafeUrlError(Exception):
    pass


def validate_https_webhook(url: str, *, allow_private: bool = False) -> None:
    """Reject anything that isn't a public https URL.

    `allow_private=True` is an escape hatch for tests against localhost; production
    callers should leave it False so SSRF defenses stay on.
    """
    parsed = urlparse(url)
    if parsed.scheme not in WEBHOOK_SCHEMES:
        raise UnsafeUrlError(
            f"webhook scheme must be one of {WEBHOOK_SCHEMES}, got {parsed.scheme!r}"
        )
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError(f"webhook URL is missing a host: {url!r}")
    if not allow_private and _resolves_to_unsafe(host):
        raise UnsafeUrlError(
            f"webhook host {host!r} resolves to a private/loopback/link-local address"
        )


def validate_rtsp_url(url: str, *, allow_private: bool = True) -> None:
    """RTSP URLs typically point at private LAN cameras, so private IPs are allowed
    by default. We still enforce the scheme allow-list to block file://, http://, etc."""
    parsed = urlparse(url)
    if parsed.scheme not in RTSP_SCHEMES:
        raise UnsafeUrlError(
            f"only {RTSP_SCHEMES} URLs allowed; got {parsed.scheme!r}"
        )
    if not parsed.hostname:
        raise UnsafeUrlError(f"RTSP URL is missing a host: {url!r}")


def _resolves_to_unsafe(host: str) -> bool:
    """Return True if `host` (literal IP or hostname) resolves to something we won't talk to."""
    try:
        ip = ipaddress.ip_address(host)
        return _is_unsafe_ip(ip)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True  # unresolvable — treat as unsafe rather than letting httpx try
    for family, _, _, _, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except (ValueError, IndexError):
            continue
        if _is_unsafe_ip(ip):
            return True
    return False


def _is_unsafe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )
