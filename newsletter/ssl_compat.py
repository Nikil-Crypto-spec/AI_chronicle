"""SSL configuration shim for corporate networks with custom CA chains.

Two opt-ins, both controlled by env vars (and exposed in `Settings`):

- `CA_BUNDLE=<path>`  -> use this PEM bundle for httpx + urllib (feedparser).
                        The right thing to do on managed Windows boxes: point
                        this at your corporate root CA bundle.
- `INSECURE_SSL=true` -> disable verification globally with a loud warning.
                        Last-resort escape hatch; do NOT leave this on.

Call `apply_ssl_config(settings)` once at startup. It mutates process-global
state (urllib's default HTTPS context, env vars consumed by httpx, certifi),
so anything that uses standard SSL machinery picks it up automatically.

`build_httpx_client(settings, **kwargs)` returns a pre-configured `httpx.Client`
that respects the same settings; collectors / fulltext use it.
"""

from __future__ import annotations

import logging
import os
import ssl
import warnings
from pathlib import Path

import httpx

from .config import Settings

log = logging.getLogger(__name__)

_APPLIED = False


def apply_ssl_config(settings: Settings) -> None:
    """Mutate process-global SSL config based on settings. Idempotent."""
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True

    if settings.insecure_ssl:
        warnings.warn(
            "INSECURE_SSL=true: TLS certificate verification is DISABLED. "
            "Do not use this against untrusted networks; it defeats HTTPS.",
            stacklevel=2,
        )
        log.warning(
            "SSL: verification DISABLED globally (INSECURE_SSL=true). "
            "Use CA_BUNDLE for a secure fix instead."
        )
        ssl._create_default_https_context = ssl._create_unverified_context  # type: ignore[attr-defined]
        try:
            import urllib3  # noqa: WPS433  (transitive via httpx/requests)

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:
            pass
        return

    bundle = (settings.ca_bundle or "").strip()
    if not bundle:
        return

    path = Path(bundle).expanduser()
    if not path.is_file():
        log.warning("CA_BUNDLE=%s does not exist; ignoring.", bundle)
        return

    log.info("SSL: using custom CA bundle %s", path)
    pem = str(path)
    os.environ.setdefault("SSL_CERT_FILE", pem)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", pem)
    os.environ.setdefault("CURL_CA_BUNDLE", pem)
    ctx = ssl.create_default_context(cafile=pem)
    ssl._create_default_https_context = lambda *a, **k: ctx  # type: ignore[assignment]


def httpx_verify(settings: Settings) -> bool | str:
    """Value to pass as `verify=` to httpx for the current settings."""
    if settings.insecure_ssl:
        return False
    bundle = (settings.ca_bundle or "").strip()
    if bundle and Path(bundle).expanduser().is_file():
        return str(Path(bundle).expanduser())
    return True


def build_httpx_client(settings: Settings, **kwargs) -> httpx.Client:
    """Construct an `httpx.Client` honouring CA_BUNDLE / INSECURE_SSL."""
    kwargs.setdefault("verify", httpx_verify(settings))
    return httpx.Client(**kwargs)
