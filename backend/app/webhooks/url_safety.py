"""Webhook URL safety / SSRF guard.

Webhook destinations are attacker-influenced: a tenant can register any URL.
Without validation that's a server-side request forgery vector — an attacker
points a webhook at cloud metadata (169.254.169.254), localhost, or internal
RFC-1918 ranges and uses our delivery worker as a proxy into the private
network. This validator rejects those before a subscription is ever stored.

Resolution is best-effort at validation time; the delivery worker should also
pin/re-check in a hardened deployment, but blocking obvious targets at the door
removes the easy attack.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeWebhookURL(ValueError):
    pass


_BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal"}
_ALLOWED_SCHEMES = {"https", "http"}


def _is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def validate_webhook_url(url: str, *, allow_http: bool = False, resolve: bool = True) -> str:
    """Return the URL if safe, else raise UnsafeWebhookURL.

    - scheme must be https (http only if explicitly allowed, e.g. dev)
    - host must be present and not a known-internal name
    - host must not be (or resolve to) a private/loopback/link-local/metadata IP
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UnsafeWebhookURL(f"Unsupported scheme: {scheme or '(none)'}")
    if scheme == "http" and not allow_http:
        raise UnsafeWebhookURL("http is not allowed; use https")

    host = parsed.hostname
    if not host:
        raise UnsafeWebhookURL("URL has no host")
    if host.lower() in _BLOCKED_HOSTNAMES:
        raise UnsafeWebhookURL("Host is not allowed")

    # If the host is a literal IP, check it directly.
    is_literal_ip = True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        is_literal_ip = False

    if is_literal_ip:
        if _is_private_ip(host):
            raise UnsafeWebhookURL("URL targets a private/internal address")
        return url

    if resolve:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            raise UnsafeWebhookURL(f"Host does not resolve: {host}") from exc
        for info in infos:
            ip = info[4][0]
            if _is_private_ip(ip):
                raise UnsafeWebhookURL("URL resolves to a private/internal address")
    return url
