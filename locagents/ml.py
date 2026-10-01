"""Agent ML/IA : écrit, exécute et débogue du code dans un bac à sable (dossier workspace/)."""
from __future__ import annotations

import subprocess
import sys

from . import config
from .agent import Agent


def _safe(rel_path: str):
    root = config.WORKSPACE.resolve()
    p = (root / rel_path).resolve()
    if p != root and root not in p.parents:
        raise ValueError("Chemin refusé : en dehors du dossier workspace/")
    return p


def list_files(subdir: str = ".") -> str:
    """Liste les fichiers du workspace.

    Args:
        subdir: Sous-dossier à lister (défaut : racine du workspace).
    """
    base = _safe(subdir)
    files = sorted(str(p.relative_to(config.WORKSPACE)) for p in base.rglob("*") if p.is_file())
    return "\n".join(files[:200]) or "(workspace vide)"


def read_file(path: str) -> str:
    """Lit un fichier texte du workspace.

    Args:
        path: Chemin relatif au workspace.
    """
    return _safe(path).read_text(encoding="utf-8", errors="replace")


def write_file(path: str, content: str) -> str:
    """Écrit (ou remplace) un fichier dans le workspace.

    Args:
        path: Chemin relatif au workspace (ex. train.py).
        content: Contenu complet du fichier.
    """
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"{len(content)} caractères écrits dans {path}"


def run_python(path: str, timeout: int = 120) -> str:
    """Exécute un script Python du workspace avec l'environnement courant et renvoie stdout/stderr.

    Args:
        path: Chemin relatif du script (ex. train.py).
        timeout: Durée maximale en secondes (défaut 120).
    """
    p = _safe(path)
    try:
        r = subprocess.run(
            [sys.executable, str(p)], cwd=config.WORKSPACE,
            capture_output=True, text=True, timeout=int(timeout),
        )
    except subprocess.TimeoutExpired:
        return f"Timeout après {timeout}s. Réduis les données/epochs ou augmente le timeout."
    return f"code de sortie : {r.returncode}\n--- stdout ---\n{r.stdout[-3000:]}\n--- stderr ---\n{r.stderr[-3000:]}"


def build_agent() -> Agent:
    return Agent(
        name="Agent ML/IA",
        model=config.MODEL_CODE,
        system=config.load_prompt("ml"),
        tools=[list_files, read_file, write_file, run_python],
        temperature=0.1,
        max_steps=12,
    )
