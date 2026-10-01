"""Client MCP (stdio) pour le pont DaVinci Resolve (wassermanproductions/unofficial-davinci-mcp).

Ce pont tourne comme un simple processus Python externe — il ne dépend PAS du scripting interne
de Resolve (Workspace > Scripts), qui s'est révélé verrouillé sur les éditions Free récentes.
Il détecte automatiquement deux modes :
  - "live"        : Resolve Studio ouvert et accessible -> pilotage direct (timelines, rendu...)
  - "interchange" : Resolve Free ou fermé -> génère des fichiers FCPXML/EDL/CSV à importer
    manuellement (File > Import > Timeline), sans jamais toucher au scripting bloqué.

Appelle toujours resolve_capabilities en premier pour savoir dans quel mode on se trouve.
"""
from __future__ import annotations

import asyncio
import json
import shutil

from . import config

# Commande pour lancer le serveur MCP. Le paquet s'installe via
# scripts/setup_resolve_bridge.sh (pip install depuis GitHub) et expose normalement
# la commande "unofficial-davinci-mcp" ; à défaut on retombe sur "python -m davinci_mcp".
_CANDIDATES = [["unofficial-davinci-mcp"], ["python", "-m", "davinci_mcp"]]


class ResolveBridgeError(RuntimeError):
    pass


def _resolve_command() -> list[str]:
    for cmd in _CANDIDATES:
        if shutil.which(cmd[0]):
            return cmd
    # Pas trouvé sur le PATH : on tente quand même "python -m davinci_mcp" avec l'interpréteur
    # du venv courant, au cas où le paquet est installé mais sans entry point exposé.
    import sys
    return [sys.executable, "-m", "davinci_mcp"]


async def _with_session(fn):
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as e:
        raise ResolveBridgeError(
            "Le paquet 'mcp' n'est pas installé. Lance : pip install mcp "
            "(ou relance scripts/setup_resolve_bridge.sh)."
        ) from e

    cmd = _resolve_command()
    params = StdioServerParameters(command=cmd[0], args=cmd[1:])
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await fn(session)
    except FileNotFoundError as e:
        raise ResolveBridgeError(
            "Le pont DaVinci Resolve n'est pas installé. Lance d'abord : "
            "./scripts/setup_resolve_bridge.sh"
        ) from e


def _run(coro_fn):
    try:
        return asyncio.run(_with_session(coro_fn))
    except ResolveBridgeError:
        raise
    except Exception as e:
        raise ResolveBridgeError(
            f"Erreur de connexion au pont ({type(e).__name__}: {e}). "
            f"Vérifie l'installation avec : python run.py resolve list-tools"
        ) from e


# ----------------------------------------------------------------------
def list_resolve_tools() -> str:
    """Liste tous les outils disponibles côté DaVinci Resolve (import, timeline, couleur, rendu, mixage...).

    À utiliser en premier pour découvrir les noms exacts avant d'appeler call_resolve_tool.
    """
    async def _go(session):
        result = await session.list_tools()
        return result.tools

    tools = _run(_go)
    lines = [f"{len(tools)} outils disponibles :"]
    for t in tools:
        desc = (t.description or "").split("\n")[0][:110]
        lines.append(f"- {t.name} : {desc}")
    return "\n".join(lines)


def describe_resolve_tool(name: str) -> str:
    """Affiche le schéma d'arguments détaillé d'un outil Resolve précis (obtenu via list_resolve_tools).

    Args:
        name: Nom exact de l'outil (ex. 'resolve_capabilities', 'generate_fcpxml').
    """
    async def _go(session):
        result = await session.list_tools()
        for t in result.tools:
            if t.name == name:
                return t
        return None

    t = _run(_go)
    if t is None:
        return f"Outil '{name}' introuvable. Utilise list_resolve_tools pour voir les noms exacts."
    schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)
    return f"{t.name}\n{t.description}\n\nSchéma des arguments :\n{json.dumps(schema, indent=2, ensure_ascii=False)}"


def call_resolve_tool(name: str, arguments_json: str = "{}") -> str:
    """Appelle un outil DaVinci Resolve précis avec ses arguments (JSON).

    La plupart des outils qui modifient quelque chose acceptent dry_run (défaut true, ne fait
    que prévisualiser) et confirm (à mettre à true avec dry_run=false pour appliquer réellement).

    Args:
        name: Nom exact de l'outil (voir list_resolve_tools).
        arguments_json: Arguments en JSON, ex. '{"paths": ["/path/clip.mov"]}'. Défaut '{}'.
    """
    try:
        args = json.loads(arguments_json) if arguments_json.strip() else {}
    except json.JSONDecodeError as e:
        return f"JSON invalide dans arguments_json : {e}"

    async def _go(session):
        return await session.call_tool(name, args)

    result = _run(_go)
    parts = [getattr(block, "text", str(block)) for block in result.content]
    text = "\n".join(parts) or "(pas de contenu retourné)"
    if getattr(result, "isError", False):
        return f"⚠️ Erreur côté outil '{name}' :\n{text}"
    return text