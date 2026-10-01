import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_GENERAL = os.getenv("MODEL_GENERAL", "qwen2.5:7b")
MODEL_CODE = os.getenv("MODEL_CODE", "qwen2.5-coder:7b")
MODEL_EMBED = os.getenv("MODEL_EMBED", "nomic-embed-text")
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))
TTS_VOICE = os.getenv("TTS_VOICE", "Thomas")

PROMPTS = ROOT / "prompts"
OUTPUTS = ROOT / "outputs"      # tout ce que les agents produisent (CSV, vidéos, audits)
WORKSPACE = ROOT / "workspace"  # bac à sable de l'agent ML (il ne peut lire/écrire que là)

for _d in (OUTPUTS, WORKSPACE):
    _d.mkdir(exist_ok=True)


def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8").strip()
