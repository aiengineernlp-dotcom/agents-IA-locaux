"""Agent Montage (DaVinci Resolve) : pilote Resolve via le pont MCP wassermanproductions/unofficial-davinci-mcp,
et peut traduire des sous-titres lui-même (aucun outil DaVinci ne sait traduire, seulement transcrire).

Fonctionne avec DaVinci Resolve Free (génère des fichiers FCPXML/EDL à importer) ET Studio
(pilotage direct), détecté automatiquement via l'outil resolve_capabilities.
Prérequis : ./scripts/setup_resolve_bridge.sh
"""
from __future__ import annotations

from . import config
from .agent import Agent
from .resolve_mcp import call_resolve_tool, describe_resolve_tool, list_resolve_tools
from .subtitles import translate_srt


def build_agent() -> Agent:
    return Agent(
        name="Agent Montage (DaVinci Resolve)",
        model=config.MODEL_CODE,
        system=config.load_prompt("video_resolve"),
        tools=[list_resolve_tools, describe_resolve_tool, call_resolve_tool, translate_srt],
        temperature=0.2,
        max_steps=14,
    )
