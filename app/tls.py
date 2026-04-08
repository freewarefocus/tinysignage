"""TLS certificate utilities for TinySignage.

Handles self-signed certificate generation and SPKI fingerprint computation
for use with Chromium's ``--ignore-certificate-errors-spki-list`` flag.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import ipaddress
import logging
import os
import socket
import sys
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)


def _default_hostnames() -> list[str]:
    """Return a reasonable default set of hostnames for the local machine."""
    names = ["localhost"]
    try:
        hn = socket.gethostname()
        if hn and hn not in names:
            names.append(hn)
        fq = socket.getfqdn()
        if fq and fq not in names:
            names.append(fq)
    except OSError:
        pass
    return names


def _default_ip_addresses() -> list[str]:
    """Return a reasonable default set of IPs for the local machine."""
    ips = ["127.0.0.1", "::1"]
    try:
        for res in socket.getaddrinfo(socket.gethostname(), None):
            addr = res[4][0]
            # Strip scope id from IPv6
            if "%" in addr:
                addr = addr.split("%", 1)[0]
            if addr not in ips:
                ips.append(addr)
    except OSError:
        pass
    return ips


def ensure_cert(
    cert_path: str | os.PathLike,
    key_path: str | os.PathLike,
    hostnames: Iterable[str] | None = None,
    ip_addresses: Iterable[str] | None = None,
) -> None:
    """Ensure a self-signed cert/key pair exists at the given paths.

    If both files already exist, returns without regenerating.
    Otherwise generates a 10-year RSA-2048 self-signed certificate with
    SANs for the given hostnames and IPs, writes them to disk (key with
    mode 0o600), and logs the SHA-256 fingerprint so the admin can pin it.
    """
    cert_path = Path(cert_path)
    key_path = Path(key_path)

    if cert_path.exists() and key_path.exists():
        return

    # Import lazily — cryptography is a heavy dep and we only need it here.
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "The 'cryptography' package is required for HTTPS support. "
            "Install it with: pip install cryptography"
        ) from e

    hostnames = list(hostnames) if hostnames else _default_hostnames()
    ip_strs = list(ip_addresses) if ip_addresses else _default_ip_addresses()

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    log.info(
        "Generating self-signed TLS certificate at %s (hostnames=%s, ips=%s)",
        cert_path, hostnames, ip_strs,
    )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostnames[0]),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TinySignage"),
    ])

    san_entries: list[x509.GeneralName] = []
    for name in hostnames:
        san_entries.append(x509.DNSName(name))
    for ip in ip_strs:
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except (ValueError, TypeError):
            continue

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True,
        )
        .sign(private_key=key, algorithm=hashes.SHA256())
    )

    cert_bytes = cert.public_bytes(serialization.Encoding.PEM)
    key_bytes = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    cert_path.write_bytes(cert_bytes)
    key_path.write_bytes(key_bytes)

    # Restrict key permissions where the OS supports it.
    try:
        os.chmod(key_path, 0o600)
    except (OSError, NotImplementedError):
        pass

    fingerprint = hashlib.sha256(
        cert.public_bytes(serialization.Encoding.DER)
    ).hexdigest()
    fp_colon = ":".join(
        fingerprint[i : i + 2].upper() for i in range(0, len(fingerprint), 2)
    )
    msg = (
        f"TinySignage TLS: generated self-signed cert at {cert_path}\n"
        f"  SHA-256 fingerprint: {fp_colon}"
    )
    log.info(msg)
    print(msg, file=sys.stderr)


def compute_spki_sha256(cert_path: str | os.PathLike) -> str:
    """Return base64(SHA-256(SubjectPublicKeyInfo)) for ``cert_path``.

    This is the format Chromium expects for
    ``--ignore-certificate-errors-spki-list``.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "The 'cryptography' package is required for HTTPS support."
        ) from e

    cert = x509.load_pem_x509_certificate(Path(cert_path).read_bytes())
    spki_der = cert.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    digest = hashlib.sha256(spki_der).digest()
    return base64.b64encode(digest).decode("ascii")


def compute_cert_fingerprint_sha256(cert_path: str | os.PathLike) -> str:
    """Return the colon-separated SHA-256 fingerprint of a cert file.

    Used by the read-only Network & Security panel so the admin can
    compare against ``openssl x509 -in ... -fingerprint -sha256``.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "The 'cryptography' package is required for HTTPS support."
        ) from e

    cert = x509.load_pem_x509_certificate(Path(cert_path).read_bytes())
    der = cert.public_bytes(serialization.Encoding.DER)
    hexed = hashlib.sha256(der).hexdigest().upper()
    return ":".join(hexed[i : i + 2] for i in range(0, len(hexed), 2))
