"""
SSRF-safe URL validation for competitor crawling.

Competitor URLs are user-supplied input that drives an outbound HTTP request
from our server. Without validation an attacker could point the crawler at
loopback, private (RFC1918), link-local, or cloud-metadata endpoints and read
internal data (server-side request forgery).

The validator enforces:
  * Only http/https schemes.
  * A resolvable hostname (no empty/blank hosts).
  * The resolved IP must be a public, globally-routable address — it must NOT
    be loopback, private, link-local, reserved, multicast, or unspecified.
  * Redirects must land on equally-safe hosts (checked by the caller via the
    provided helper, since aiohttp follows redirects internally).
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse
from typing import Optional


# Schemes we are willing to crawl.
ALLOWED_SCHEMES = {"http", "https"}


class URLValidationError(Exception):
    """Raised when a URL fails SSRF-safety validation."""


def _is_public_ip(ip: ipaddress._BaseAddress) -> bool:
    """Return True only for public, globally-routable IP addresses."""
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return False
    # IPv4-mapped / 6to4 /teredo wrappers hide an inner address; unwrap it.
    if ip.version == 6 and (ip.ipv4_mapped is not None or ip.sixtofour is not None):
        inner = ip.ipv4_mapped or ip.sixtofour
        return _is_public_ip(inner)
    return True


def _resolve_and_check(hostname: str) -> None:
    """Resolve hostname and confirm every resolved IP is a public address."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise URLValidationError(f"Hostname '{hostname}' could not be resolved") from exc

    if not infos:
        raise URLValidationError(f"Hostname '{hostname}' resolved to no addresses")

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError as exc:
            raise URLValidationError(f"Hostname '{hostname}' returned invalid IP '{ip_str}'") from exc
        if not _is_public_ip(ip):
            raise URLValidationError(
                f"Hostname '{hostname}' resolves to a restricted address '{ip_str}'"
            )


def validate_crawl_url(url: str, allow_local: bool = False) -> str:
    """
    Validate a URL intended to be crawled, enforcing SSRF safety.

    Args:
        url: The URL to validate.
        allow_local: When True, skip the public-IP check so loopback / private
            addresses (e.g. 127.0.0.1) are accepted. Intended only for local
            development and end-to-end testing; must never be enabled in
            production where crawler input is untrusted.

    Returns the original URL string if it is safe.
    Raises URLValidationError with a human-readable reason otherwise.
    """
    if not url or not isinstance(url, str):
        raise URLValidationError("URL is required and must be a string")

    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise URLValidationError(
            f"URL scheme '{parsed.scheme or 'empty'}' not allowed; use http or https"
        )

    hostname = parsed.hostname
    if not hostname:
        raise URLValidationError("URL must include a hostname")

    # Reject obvious literal-IP hosts up front, then resolve hostnames.
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        # Not a literal IP — treat as a DNS name and resolve it.
        if allow_local:
            return url
        _resolve_and_check(hostname)
    else:
        # Literal IP: validate directly without a DNS round-trip.
        if not allow_local and not _is_public_ip(literal):
            raise URLValidationError(
                f"Literal IP '{hostname}' is a restricted address"
            )

    return url


def is_safe_ip(ip_str: str) -> bool:
    """Check a single resolved IP string is public (used to vet redirect targets)."""
    try:
        return _is_public_ip(ipaddress.ip_address(ip_str))
    except ValueError:
        return False
