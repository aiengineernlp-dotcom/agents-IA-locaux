"""Garde-fou de portée (scope) : tout ce que les agents cyber touchent doit être dans scope/pentest_scope.yml.

Aucune IP/hôte codé en dur : c'est TOI qui déclares ce qui est autorisé, dans le fichier YAML.
"""
from __future__ import annotations

import ipaddress
import socket

import yaml

from . import config

SCOPE_FILE = config.ROOT / "scope" / "pentest_scope.yml"


def _load_targets() -> list[str]:
    if not SCOPE_FILE.exists():
        return []
    data = yaml.safe_load(SCOPE_FILE.read_text(encoding="utf-8")) or {}
    return [str(t).strip() for t in (data.get("targets") or []) if str(t).strip()]


def _resolve(host: str) -> str | None:
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


def is_in_scope(host: str) -> bool:
    """Vrai si `host` (IP ou hostname) correspond à une entrée du fichier de scope."""
    targets = _load_targets()
    if not targets:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
        resolved = _resolve(host)
        ip_resolved = ipaddress.ip_address(resolved) if resolved else None

    for t in targets:
        if t == host:
            return True
        try:
            net = ipaddress.ip_network(t, strict=False)
        except ValueError:
            continue
        if ip is not None and ip in net:
            return True
        if ip is None and ip_resolved is not None and ip_resolved in net:
            return True
    return False


def require_in_scope(host: str) -> None:
    if not is_in_scope(host):
        raise PermissionError(
            f"'{host}' n'est pas dans scope/pentest_scope.yml — action refusée. "
            f"Ajoute cet hôte au fichier (uniquement si tu le possèdes ou as une autorisation écrite) puis relance."
        )
