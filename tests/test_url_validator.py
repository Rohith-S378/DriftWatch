"""Unit tests for SSRF-safe URL validation."""
import pytest
from app.services.url_validator import validate_crawl_url, URLValidationError, is_safe_ip


@pytest.mark.parametrize("invalid_url", [
    "",
    "   ",
    None,
    123,
    "ftp://example.com/file",
    "file:///etc/passwd",
    "gopher://example.com",
    "data:text/plain,hello",
    "http://",
    "http:///path",
])
def test_rejects_malformed_and_unsupported_schemes(invalid_url):
    with pytest.raises(URLValidationError):
        validate_crawl_url(invalid_url)


@pytest.mark.parametrize("blocked_ip", [
    # IPv4 loopback
    "http://127.0.0.1",
    "http://127.0.0.1:8080/path",
    "http://127.1.2.3",
    # RFC 1918 private
    "http://10.0.0.1",
    "http://10.255.255.255",
    "http://172.16.0.1",
    "http://172.31.255.255",
    "http://192.168.1.1",
    "http://192.168.0.254",
    # Link-local / APIPA
    "http://169.254.169.254",  # AWS/GCP/Azure metadata IP
    # Broadcast / zero / reserved
    "http://0.0.0.0",
    "http://255.255.255.255",
    "http://224.0.0.1",  # multicast
    # IPv6 loopback and link-local
    "http://[::1]",
    "http://[fe80::1]",
    "http://[fc00::1]",
])
def test_rejects_internal_and_reserved_ips(blocked_ip):
    with pytest.raises(URLValidationError):
        validate_crawl_url(blocked_ip)


@pytest.mark.parametrize("resolves_to_loopback", [
    "http://localhost",
    "http://localhost:8000",
])
def test_rejects_localhost_domain(resolves_to_loopback):
    with pytest.raises(URLValidationError):
        validate_crawl_url(resolves_to_loopback)


def test_allows_public_domain(monkeypatch):
    """When DNS resolves to a public routable IP, URL is accepted."""
    # Mock socket.getaddrinfo to avoid depending on network in tests
    import socket

    def fake_getaddrinfo(host, port):
        # 93.184.216.34 is example.com's public IP
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    result = validate_crawl_url("https://example.com/pricing")
    assert result == "https://example.com/pricing"


def test_is_safe_ip():
    assert is_safe_ip("93.184.216.34") is True
    assert is_safe_ip("127.0.0.1") is False
    assert is_safe_ip("169.254.169.254") is False
    assert is_safe_ip("not-an-ip") is False
