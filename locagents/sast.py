"""Agent SAST : audit statique de code (secrets, dépendances vulnérables, patterns dangereux) via semgrep/bandit/gitleaks/pip-audit."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from . import config
from .agent import Agent


def _run(cmd: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str, str]:
    if not shutil.which(cmd[0]):
        return 127, "", f"'{cmd[0]}' introuvable. Installe-le : brew install {cmd[0]}"
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"Timeout après {timeout}s"


def _resolve_repo(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise ValueError(f"Chemin introuvable : {p}")
    return p


def scan_secrets(repo_path: str) -> str:
    """Cherche des secrets en clair (clés API, mots de passe, tokens) dans un dépôt via gitleaks.

    Args:
        repo_path: Chemin local du dépôt à auditer.
    """
    repo = _resolve_repo(repo_path)
    code, out, err = _run(["gitleaks", "detect", "--source", str(repo), "--no-git", "-f", "json", "-r", "-"], repo)
    if code == 127:
        return err
    if not out.strip():
        return "Aucun secret détecté par gitleaks." if code == 0 else f"gitleaks : code {code}\n{err[-1000:]}"
    try:
        findings = json.loads(out)
    except json.JSONDecodeError:
        return out[-3000:]
    if not findings:
        return "Aucun secret détecté."
    lines = [f"{len(findings)} secret(s) potentiel(s) détecté(s) :"]
    for f in findings[:30]:
        lines.append(f"- [{f.get('RuleID')}] {f.get('File')}:{f.get('StartLine')} — {f.get('Description')}")
    return "\n".join(lines)


def scan_code_patterns(repo_path: str, languages: str = "auto") -> str:
    """Audit statique multi-langages (injections SQL/XSS, crypto faible, etc.) via semgrep (règles publiques 'auto').

    Args:
        repo_path: Chemin local du dépôt à auditer.
        languages: Indicatif seulement, semgrep détecte automatiquement (défaut 'auto').
    """
    repo = _resolve_repo(repo_path)
    code, out, err = _run(["semgrep", "--config", "auto", "--json", "--quiet", str(repo)], repo, timeout=600)
    if code == 127:
        return err
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return f"Sortie semgrep illisible.\n{err[-1500:]}"
    results = data.get("results", [])
    if not results:
        return "Aucun problème détecté par semgrep."
    sev_order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    results.sort(key=lambda r: sev_order.get(r.get("extra", {}).get("severity", "INFO"), 3))
    lines = [f"{len(results)} finding(s) semgrep :"]
    for r in results[:40]:
        sev = r.get("extra", {}).get("severity", "?")
        msg = r.get("extra", {}).get("message", "").split("\n")[0]
        lines.append(f"- [{sev}] {r['path']}:{r['start']['line']} ({r['check_id'].split('.')[-1]}) — {msg}")
    return "\n".join(lines)


def scan_python_security(repo_path: str) -> str:
    """Audit spécifique Python (bandit) : injections, deserialization dangereuse, usage de eval/exec, etc.

    Args:
        repo_path: Chemin local du dépôt à auditer.
    """
    repo = _resolve_repo(repo_path)
    code, out, err = _run(["bandit", "-r", str(repo), "-f", "json", "-q"], repo)
    if code == 127:
        return err
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return f"Sortie bandit illisible.\n{err[-1500:]}"
    results = data.get("results", [])
    if not results:
        return "Aucun problème détecté par bandit."
    lines = [f"{len(results)} finding(s) bandit :"]
    for r in results[:40]:
        lines.append(f"- [{r['issue_severity']}/{r['issue_confidence']}] {r['filename']}:{r['line_number']} "
                     f"({r['test_id']} {r['test_name']}) — {r['issue_text']}")
    return "\n".join(lines)


def scan_dependencies(repo_path: str) -> str:
    """Cherche des dépendances Python avec des CVE connues via pip-audit (nécessite requirements.txt ou un venv).

    Args:
        repo_path: Chemin local du dépôt (doit contenir requirements.txt).
    """
    repo = _resolve_repo(repo_path)
    req = repo / "requirements.txt"
    if not req.exists():
        return "Aucun requirements.txt trouvé dans ce dépôt."
    code, out, err = _run(["pip-audit", "-r", str(req), "-f", "json"], repo, timeout=180)
    if code == 127:
        return err
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return f"Sortie pip-audit illisible.\n{err[-1500:]}"
    deps = [d for d in data.get("dependencies", data if isinstance(data, list) else []) if d.get("vulns")]
    if not deps:
        return "Aucune CVE connue trouvée dans les dépendances."
    lines = [f"{len(deps)} dépendance(s) vulnérable(s) :"]
    for d in deps:
        ids = ", ".join(v["id"] for v in d["vulns"][:3])
        lines.append(f"- {d['name']} {d['version']} → {ids}")
    return "\n".join(lines)


def full_audit(repo_path: str) -> str:
    """Lance l'audit complet (secrets + patterns + bandit + dépendances) et enregistre un rapport Markdown.

    Args:
        repo_path: Chemin local du dépôt à auditer.
    """
    repo = _resolve_repo(repo_path)
    sections = {
        "Secrets (gitleaks)": scan_secrets(repo_path),
        "Patterns de vulnérabilités (semgrep)": scan_code_patterns(repo_path),
        "Sécurité Python (bandit)": scan_python_security(repo_path),
        "Dépendances vulnérables (pip-audit)": scan_dependencies(repo_path),
    }
    report = [f"# Audit SAST — {repo.name}\n"]
    for title, content in sections.items():
        report.append(f"## {title}\n\n{content}\n")
    out = config.OUTPUTS / f"sast_{repo.name}.md"
    out.write_text("\n".join(report), encoding="utf-8")
    return f"Rapport complet : {out}\n\n" + "\n\n".join(f"### {t}\n{c}" for t, c in sections.items())


def build_agent() -> Agent:
    return Agent(
        name="Agent SAST",
        model=config.MODEL_CODE,
        system=config.load_prompt("hack"),
        tools=[scan_secrets, scan_code_patterns, scan_python_security, scan_dependencies, full_audit],
        temperature=0.1,
        max_steps=10,
    )
