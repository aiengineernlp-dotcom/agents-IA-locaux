#!/usr/bin/env bash
# Installation reproductible : dépendances système, environnement Python, modèles Ollama, agents.
set -euo pipefail
cd "$(dirname "$0")"

say() { printf "\n\033[1m▶ %s\033[0m\n" "$*"; }

say "1/5 Outils système"
command -v brew >/dev/null || { echo "Homebrew manquant : https://brew.sh"; exit 1; }
command -v ffmpeg >/dev/null || brew install ffmpeg
command -v ollama >/dev/null || { echo "Ollama manquant : installe-le depuis https://ollama.com/download (ou : brew install ollama)"; exit 1; }
command -v python3 >/dev/null || brew install python@3.11

say "1b/5 Outils SecOps (pilier Hacking/SecOps)"
for pkg in nmap semgrep gitleaks pipx; do command -v "$pkg" >/dev/null || brew install "$pkg"; done
command -v bandit >/dev/null || pipx install bandit 2>/dev/null || true
command -v pip-audit >/dev/null || pipx install pip-audit 2>/dev/null || true

say "2/5 Environnement Python (.venv)"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

say "3/5 Configuration"
[ -f .env ] || cp .env.example .env
set -a; source .env; set +a

say "4/5 Modèles Ollama"
curl -sf "${OLLAMA_HOST:-http://localhost:11434}/api/tags" >/dev/null || {
  echo "Ollama ne répond pas. Ouvre l'app Ollama (ou lance 'ollama serve' dans un autre terminal) puis relance ce script."; exit 1; }
for m in "$MODEL_GENERAL" "$MODEL_CODE" "$MODEL_EMBED"; do ollama pull "$m"; done

say "5/5 Création des agents dans Ollama"
python scripts/create_ollama_agents.py

say "Vérification"
python run.py doctor

cat <<'MSG'

✅ Terminé. Pour l'utiliser :
   source .venv/bin/activate
   python run.py seo chat        (ou : ml chat / video chat)
Interface graphique (optionnel, Docker Desktop requis) :
   docker compose up -d   →   http://localhost:3000
MSG

#
#source .venv/bin/activate
#python run.py doctor
#
#
#python run.py seo chat
#
#
#Dans le chat, tape une question simple, genre bonjour, laisse-le répondre, puis dans un autre onglet de terminal (ou après avoir tapé /quit) :
#
#ollama ps