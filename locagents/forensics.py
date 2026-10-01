"""Agent Forensics/Threat Intel : parsing de logs, détection d'anomalies, règles Sigma/YARA sur TES fichiers.

Aucune action réseau ici — uniquement de l'analyse de fichiers déjà sur le disque.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import yaml

from . import config
from .agent import Agent

# Patterns génériques (SSH, auth, web) pour un premier passage sans dépendance lourde.
SSH_FAIL = re.compile(r"Failed password.*from (?P<ip>\d{1,3}(?:\.\d{1,3}){3})")
SSH_INVALID = re.compile(r"Invalid user (?P<user>\S+) from (?P<ip>\d{1,3}(?:\.\d{1,3}){3})")
WEB_LOG = re.compile(
    r'(?P<ip>\d{1,3}(?:\.\d{1,3}){3}).*?"(?P<method>[A-Z]+) (?P<path>\S+).*?" (?P<status>\d{3})'
)
SUSPICIOUS_PATH = re.compile(
    r"(\.\./|/etc/passwd|union\s+select|<script|;--|/wp-login|/xmlrpc\.php|\bcmd=|base64_decode)", re.I
)


def _resolve(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise ValueError(f"Fichier introuvable : {p}")
    return p


def analyze_auth_log(path: str, top: int = 15) -> str:
    """Analyse un log d'authentification (style /var/log/auth.log ou secure.log) : brute-force, utilisateurs invalides.

    Args:
        path: Chemin du fichier de log.
        top: Nombre d'IP les plus actives à afficher (défaut 15).
    """
    p = _resolve(path)
    fails, invalid_users = Counter(), Counter()
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = SSH_FAIL.search(line)
        if m:
            fails[m["ip"]] += 1
        m = SSH_INVALID.search(line)
        if m:
            invalid_users[m["user"]] += 1

    lines = [f"{sum(fails.values())} échecs de mot de passe, {len(fails)} IP distinctes."]
    for ip, n in fails.most_common(int(top)):
        flag = " ⚠️ brute-force probable" if n >= 10 else ""
        lines.append(f"- {ip} : {n} échec(s){flag}")
    if invalid_users:
        lines.append(f"\nUtilisateurs invalides testés (scan de comptes) : {sum(invalid_users.values())} tentatives")
        for user, n in invalid_users.most_common(10):
            lines.append(f"- {user} : {n}")
    return "\n".join(lines)


def analyze_web_log(path: str, top: int = 15) -> str:
    """Analyse un log web (Apache/Nginx combined) : requêtes suspectes, codes d'erreur, IP les plus actives.

    Args:
        path: Chemin du fichier de log.
        top: Nombre d'entrées à afficher par catégorie (défaut 15).
    """
    p = _resolve(path)
    ip_counter, status_counter = Counter(), Counter()
    suspicious = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = WEB_LOG.search(line)
        if not m:
            continue
        ip_counter[m["ip"]] += 1
        status_counter[m["status"]] += 1
        if SUSPICIOUS_PATH.search(m["path"]):
            suspicious.append(f"{m['ip']} {m['method']} {m['path'][:120]} → {m['status']}")

    lines = [f"{sum(ip_counter.values())} requêtes, {len(ip_counter)} IP distinctes."]
    lines.append("\nTop IP :")
    for ip, n in ip_counter.most_common(int(top)):
        lines.append(f"- {ip} : {n} requêtes")
    lines.append("\nCodes de statut :")
    for status, n in status_counter.most_common(10):
        lines.append(f"- {status} : {n}")
    if suspicious:
        lines.append(f"\n⚠️ {len(suspicious)} requête(s) au pattern suspect (traversal, injection, scan de endpoints) :")
        lines.extend(f"- {s}" for s in suspicious[:30])
    return "\n".join(lines)


def search_iocs(path: str, iocs: str) -> str:
    """Cherche une liste d'IOC (IP, domaines, hash, chaînes) dans un fichier, ligne par ligne.

    Args:
        path: Chemin du fichier à inspecter.
        iocs: IOC séparés par des virgules (ex. "1.2.3.4, evil.example.com, 4d5e6f...").
    """
    p = _resolve(path)
    needles = [i.strip() for i in iocs.split(",") if i.strip()]
    if not needles:
        return "Aucun IOC fourni."
    hits = {n: [] for n in needles}
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for n in needles:
            if n in line:
                hits[n].append(i)
    lines = []
    for n, ln in hits.items():
        lines.append(f"- {n} : {len(ln)} occurrence(s)" + (f" (lignes {ln[:10]})" if ln else ""))
    return "\n".join(lines)


def generate_sigma_rule(title: str, description: str, log_source: str, pattern: str) -> str:
    """Génère une règle Sigma (détection générique multi-SIEM) à partir d'une observation, et l'enregistre.

    Args:
        title: Titre court de la règle.
        description: Ce que la règle détecte et pourquoi.
        log_source: Type de source (ex. "linux-auth", "apache-access", "windows-security").
        pattern: Le motif/texte à détecter dans le champ principal du log.
    """
    rule = {
        "title": title,
        "description": description,
        "status": "experimental",
        "logsource": {"category": log_source},
        "detection": {"selection": {"keywords": [pattern]}, "condition": "selection"},
        "level": "medium",
    }
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:50]
    out = config.OUTPUTS / f"sigma_{slug}.yml"
    out.write_text(yaml.safe_dump(rule, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return f"Règle Sigma enregistrée : {out}"


def build_agent() -> Agent:
    return Agent(
        name="Agent Forensics / Threat Intel",
        model=config.MODEL_CODE,
        system=config.load_prompt("hack"),
        tools=[analyze_auth_log, analyze_web_log, search_iocs, generate_sigma_rule],
        temperature=0.2,
    )
