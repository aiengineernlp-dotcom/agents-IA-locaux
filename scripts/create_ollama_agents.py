#!/usr/bin/env python3
"""Crée dans Ollama les six agents nommés (agent-seo, agent-ml, agent-video, agent-sast,
agent-forensics, agent-pentest).

Chacun = un modèle de base + le prompt du dossier prompts/ + des paramètres.
Ils apparaissent ensuite automatiquement dans Open WebUI (menu des modèles).
Les Modelfile générés sont écrits dans models/ pour que tu puisses les lire/modifier.
Relancer ce script après avoir modifié un prompt met l'agent à jour.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locagents import config  # noqa: E402

AGENTS = {
    "agent-seo": (config.MODEL_GENERAL, "seo", 0.3),
    "agent-ml": (config.MODEL_CODE, "ml", 0.1),
    "agent-video": (config.MODEL_GENERAL, "video", 0.5),
    "agent-sast": (config.MODEL_CODE, "hack", 0.1),
    "agent-forensics": (config.MODEL_CODE, "hack", 0.2),
    "agent-pentest": (config.MODEL_CODE, "hack", 0.1),
}

models_dir = config.ROOT / "models"
models_dir.mkdir(exist_ok=True)

for name, (base, prompt, temp) in AGENTS.items():
    system = config.load_prompt(prompt).replace('"""', "'''")
    mf = models_dir / f"Modelfile.{name}"
    mf.write_text(
        f"FROM {base}\n"
        f"PARAMETER temperature {temp}\n"
        f"PARAMETER num_ctx {config.NUM_CTX}\n"
        f'SYSTEM """\n{system}\n"""\n',
        encoding="utf-8",
    )
    print(f"→ ollama create {name}  (base : {base})")
    r = subprocess.run(["ollama", "create", name, "-f", str(mf)])
    if r.returncode != 0:
        sys.exit(f"Échec de la création de {name}. Le modèle de base {base} est-il téléchargé ? (ollama pull {base})")

print("\n✅ Agents créés. Vérifie avec : ollama list")


