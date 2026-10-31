"""Explicit file grants and public HTTPS destinations with connection-time IP pinning."""

import http.client
import ipaddress
import os
import socket
import ssl
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from veya.domain.models import DomainError


def granted_bytes(root: Path, relative: str, maximum: int = 524288) -> bytes:
    if type(maximum) is not int or not 0 < maximum <= 1048576:
        raise ValueError('Explicit bounded input size required')
    parts = PurePosixPath(relative).parts
    if (
        not parts
        or any(p in {'.', '..'} for p in parts)
        or relative.startswith('/')
        or '\\' in relative
        or ':' in relative
        or '\x00' in relative
    ):
        raise DomainError('forbidden', 'Path is outside its grant')
    root = root.resolve(strict=True)
    candidate = root
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink() or bool(getattr(candidate, 'is_junction', lambda: False)()):
            raise DomainError('forbidden', 'Links are not granted inputs')
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise DomainError('forbidden', 'Path is outside its grant')
    before = resolved.stat()
    with resolved.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise DomainError('forbidden', 'Input changed while opening')
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise DomainError('too_large', 'Granted input exceeds its byte limit')
    return data


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname: str, address: str, port: int):
        self.context = ssl.create_default_context()
        super().__init__(hostname, port, timeout=10, context=self.context)
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, self.port), self.timeout)
        try:
            self.sock = self.context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def public_addresses(url: str) -> tuple[str, str, int, str]:
    parsed = urlsplit(url)
    if (
        parsed.scheme != 'https'
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or any(ord(c) < 33 for c in url)
    ):
        raise DomainError('forbidden', 'A public HTTPS destination is required')
    port = parsed.port or 443
    addresses = {
        str(entry[4][0])
        for entry in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    }
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise DomainError('forbidden', 'Destination resolves outside the public network')
    target = parsed.path or '/'
    if parsed.query:
        target += '?' + parsed.query
    return parsed.hostname, sorted(addresses)[0], port, target


def https_request(url: str, payload: bytes, headers: dict[str, str]) -> bytes:
    host, address, port, target = public_addresses(url)
    if len(payload) > 1048576 or any(
        k.lower() in {'host', 'connection', 'content-length'} for k in headers
    ):
        raise DomainError('invalid_input', 'Invalid outbound request')
    connection = PinnedHTTPS(host, address, port)
    try:
        connection.request('POST', target, payload, headers)
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            # No redirects: credentials can never be forwarded to another origin.
            raise DomainError('unavailable', 'Remote endpoint rejected the request')
        result = response.read(1048577)
        if len(result) > 1048576:
            raise DomainError('too_large', 'Remote output exceeds its byte limit')
        return result
    finally:
        connection.close()
