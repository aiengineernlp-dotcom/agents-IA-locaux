"""Traduction de sous-titres .srt : garde les timecodes intacts, ne traduit que le texte.

Un outil séparé volontairement simple (pas de LLM-agent-avec-outils) : sur un fichier structuré
comme un .srt, un appel direct au modèle est plus fiable qu'une boucle d'agent qui pourrait
se perdre ou halluciner un nom d'outil.
"""
from __future__ import annotations

import re
from pathlib import Path

import ollama

from . import config

client = ollama.Client(host=config.OLLAMA_HOST)

_BLOCK_RE = re.compile(
    r"(?P<index>\d+)\s*\n(?P<time>\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\s*\n(?P<text>.*?)(?=\n\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}|\Z)",
    re.DOTALL,
)


def translate_srt(srt_path: str, target_language: str = "français", model: str | None = None) -> str:
    """Traduit un fichier .srt existant en gardant exactement les mêmes timecodes.

    Args:
        srt_path: Chemin du fichier .srt source (langue d'origine).
        target_language: Langue cible en toutes lettres (défaut 'français').
        model: Modèle Ollama à utiliser (défaut celui de la config, MODEL_GENERAL).
    """
    p = Path(srt_path).expanduser()
    if not p.exists():
        raise ValueError(f"Fichier introuvable : {p}")
    model = model or config.MODEL_GENERAL

    raw = p.read_text(encoding="utf-8")
    blocks = _BLOCK_RE.findall(raw)
    if not blocks:
        raise ValueError("Aucun bloc de sous-titre reconnu — le fichier est-il bien un .srt valide ?")

    out_lines = []
    for index, timecode, text in blocks:
        text = text.strip()
        prompt = (
            f"Traduis ce sous-titre en {target_language}. Réponds UNIQUEMENT avec la traduction, "
            f"rien d'autre (pas de guillemets, pas d'explication), en gardant le même nombre de "
            f"lignes si possible :\n\n{text}"
        )
        resp = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2},
        )
        translated = resp.message.content.strip()
        out_lines.append(f"{index}\n{timecode}\n{translated}\n")

    out_path = p.with_name(p.stem + f"_{target_language[:2].lower()}" + p.suffix)
    out_path.write_text("\n".join(out_lines), encoding="utf-8")
    return f"{len(blocks)} sous-titres traduits en {target_language} → {out_path}"
