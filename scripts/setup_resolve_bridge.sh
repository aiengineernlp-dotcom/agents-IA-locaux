#!/usr/bin/env bash
# Installe le pont MCP pour DaVinci Resolve (projet communautaire wassermanproductions/unofficial-davinci-mcp).
# Détecte automatiquement Studio (pilotage direct) vs Free (génère des fichiers FCPXML/EDL à importer).
# Ne touche à rien dans Resolve : s'installe comme un paquet Python normal.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▶ 1/3 Installation du pont (unofficial-davinci-mcp)"
source .venv/bin/activate
pip install "git+https://github.com/wassermanproductions/unofficial-davinci-mcp.git"

echo "▶ 2/3 Vérification de ffmpeg (seule dépendance non-Python)"
command -v ffmpeg >/dev/null || { echo "ffmpeg manquant : brew install ffmpeg"; exit 1; }

echo "▶ 3/3 Vérification que la commande est bien accessible"
if ! command -v unofficial-davinci-mcp >/dev/null; then
  echo "⚠️  La commande 'unofficial-davinci-mcp' n'est pas sur le PATH."
  echo "    Pas grave : le client Python utilisera 'python -m davinci_mcp' à la place."
fi

cat <<'MSG'

✅ Terminé. Aucune manipulation nécessaire dans DaVinci Resolve (pas de Workspace > Scripts,
   contrairement à l'ancienne méthode) : le pont tourne comme un processus externe.

Pour l'utiliser :
   source .venv/bin/activate
   python run.py resolve list-tools          # doit lister ~23 outils
   python run.py resolve call resolve_capabilities '{}'   # dit si tu es en tier "live" ou "interchange"
MSG
