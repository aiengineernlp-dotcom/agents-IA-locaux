#!/usr/bin/env python3
"""Point d'entrée unique.

  python run.py doctor
  python run.py seo chat | audit URL | crawl URL [--max 30] | serp "requête" | cluster fichier.csv [--k 8]
  python run.py ml chat | task "consigne"
  python run.py video chat | make "sujet" [--scenes 5] [--voice Thomas] | render chemin/scenes.json
  python run.py sast chat | audit REPO | secrets REPO | code REPO | deps REPO
  python run.py forensics chat | auth FICHIER | web FICHIER | ioc FICHIER "1.2.3.4, evil.com"
  python run.py pentest chat | scope | check HOST | scan HOST [--ports 1-1000] | vuln HOST | headers HOST [--port 80] [--https]
  python run.py resolve chat | list-tools | describe NOM | call NOM '{"arg": "valeur"}'
  python run.py subtitles translate FICHIER.srt [--lang français]
"""
import argparse
import json
import shutil
import sys


def doctor() -> None:
    from locagents import config
    from locagents.agent import client

    print(f"Ollama : {config.OLLAMA_HOST}")
    try:
        installed = [m.model for m in client.list().models]
    except Exception as e:
        print(f"❌ Ollama injoignable ({type(e).__name__}). Lance l'app Ollama ou `ollama serve`.")
        return
    print("✅ Ollama répond")
    for m in (config.MODEL_GENERAL, config.MODEL_CODE, config.MODEL_EMBED):
        ok = m in installed or f"{m}:latest" in installed
        print(("✅" if ok else "❌") + f" modèle {m}" + ("" if ok else f"   → ollama pull {m}"))
    for a in ("agent-seo", "agent-ml", "agent-video", "agent-sast", "agent-forensics", "agent-pentest"):
        print(("✅" if f"{a}:latest" in installed else "⚠️ ") + f" {a}" + ("" if f"{a}:latest" in installed else "   → python scripts/create_ollama_agents.py"))
    for tool in ("ffmpeg", "say", "docker", "nmap", "semgrep", "bandit", "gitleaks", "pip-audit"):
        print(("✅" if shutil.which(tool) else "⚠️ ") + f" {tool}" + ("" if shutil.which(tool) else " introuvable"))
    from pathlib import Path
    bridge = config.ROOT / "third_party" / "davinci-resolve-mcp" / "src" / "resolve_mcp_bridge.py"
    print(("✅" if bridge.exists() else "⚠️ ") + " pont DaVinci Resolve" + ("" if bridge.exists() else "   → ./scripts/setup_resolve_bridge.sh"))
    try:
        import mcp  # noqa
        print("✅ paquet mcp")
    except ImportError:
        print("⚠️  paquet mcp   → pip install mcp")
    print("\nAstuce : lance un prompt puis `ollama ps` — la colonne PROCESSOR indique si le GPU est utilisé (100% CPU = non).")


def main() -> None:
    ap = argparse.ArgumentParser(description="Agents IA locaux")
    sub = ap.add_subparsers(dest="domain", required=True)
    sub.add_parser("doctor")

    s = sub.add_parser("seo").add_subparsers(dest="cmd", required=True)
    s.add_parser("chat")
    a = s.add_parser("audit"); a.add_argument("url")
    a = s.add_parser("crawl"); a.add_argument("url"); a.add_argument("--max", type=int, default=20)
    a = s.add_parser("serp"); a.add_argument("query")
    a = s.add_parser("cluster"); a.add_argument("csv"); a.add_argument("--k", type=int, default=8); a.add_argument("--column", default="keyword")

    m = sub.add_parser("ml").add_subparsers(dest="cmd", required=True)
    m.add_parser("chat")
    a = m.add_parser("task"); a.add_argument("text")

    v = sub.add_parser("video").add_subparsers(dest="cmd", required=True)
    v.add_parser("chat")
    a = v.add_parser("make"); a.add_argument("topic"); a.add_argument("--scenes", type=int, default=5); a.add_argument("--voice", default="")
    a = v.add_parser("render"); a.add_argument("path"); a.add_argument("--voice", default="")

    sa = sub.add_parser("sast").add_subparsers(dest="cmd", required=True)
    sa.add_parser("chat")
    a = sa.add_parser("audit"); a.add_argument("repo")
    a = sa.add_parser("secrets"); a.add_argument("repo")
    a = sa.add_parser("code"); a.add_argument("repo")
    a = sa.add_parser("deps"); a.add_argument("repo")

    fo = sub.add_parser("forensics").add_subparsers(dest="cmd", required=True)
    fo.add_parser("chat")
    a = fo.add_parser("auth"); a.add_argument("path")
    a = fo.add_parser("web"); a.add_argument("path")
    a = fo.add_parser("ioc"); a.add_argument("path"); a.add_argument("iocs")

    rv = sub.add_parser("resolve").add_subparsers(dest="cmd", required=True)
    rv.add_parser("chat")
    rv.add_parser("list-tools")
    a = rv.add_parser("describe"); a.add_argument("name")
    a = rv.add_parser("call"); a.add_argument("name"); a.add_argument("args_json", nargs="?", default="{}")

    pt = sub.add_parser("pentest").add_subparsers(dest="cmd", required=True)
    pt.add_parser("chat")
    pt.add_parser("scope")
    a = pt.add_parser("check"); a.add_argument("host")
    a = pt.add_parser("scan"); a.add_argument("host"); a.add_argument("--ports", default="1-1000")
    a = pt.add_parser("vuln"); a.add_argument("host")
    a = pt.add_parser("headers"); a.add_argument("host"); a.add_argument("--port", type=int, default=80); a.add_argument("--https", action="store_true")

    st = sub.add_parser("subtitles").add_subparsers(dest="cmd", required=True)
    a = st.add_parser("translate"); a.add_argument("srt"); a.add_argument("--lang", default="français")

    args = ap.parse_args()

    if args.domain == "doctor":
        return doctor()

    if args.domain == "seo":
        from locagents import seo
        if args.cmd == "chat":
            seo.build_agent().chat()
        elif args.cmd == "audit":
            print(json.dumps(seo.audit_page(args.url), ensure_ascii=False, indent=2))
        elif args.cmd == "crawl":
            print(seo.crawl_site(args.url, args.max))
        elif args.cmd == "serp":
            print(json.dumps(seo.serp_snapshot(args.query), ensure_ascii=False, indent=2))
        elif args.cmd == "cluster":
            print(seo.cluster_keywords(args.csv, args.k, args.column))

    elif args.domain == "ml":
        from locagents import ml
        agent = ml.build_agent()
        agent.chat() if args.cmd == "chat" else print(agent.ask(args.text))

    elif args.domain == "video":
        from locagents import video
        if args.cmd == "chat":
            video.build_agent().chat()
        elif args.cmd == "make":
            print(video.make_video(args.topic, args.scenes, args.voice))
        elif args.cmd == "render":
            print(video.render_video(args.path, args.voice))

    elif args.domain == "sast":
        from locagents import sast
        if args.cmd == "chat":
            sast.build_agent().chat()
        elif args.cmd == "audit":
            print(sast.full_audit(args.repo))
        elif args.cmd == "secrets":
            print(sast.scan_secrets(args.repo))
        elif args.cmd == "code":
            print(sast.scan_code_patterns(args.repo))
        elif args.cmd == "deps":
            print(sast.scan_dependencies(args.repo))

    elif args.domain == "forensics":
        from locagents import forensics
        if args.cmd == "chat":
            forensics.build_agent().chat()
        elif args.cmd == "auth":
            print(forensics.analyze_auth_log(args.path))
        elif args.cmd == "web":
            print(forensics.analyze_web_log(args.path))
        elif args.cmd == "ioc":
            print(forensics.search_iocs(args.path, args.iocs))

    elif args.domain == "pentest":
        from locagents import pentest
        if args.cmd == "chat":
            pentest.build_agent().chat()
        elif args.cmd == "scope":
            print(pentest.list_scope())
        elif args.cmd == "check":
            print(pentest.check_scope(args.host))
        elif args.cmd == "scan":
            print(pentest.port_scan(args.host, args.ports))
        elif args.cmd == "vuln":
            print(pentest.vuln_scan(args.host))
        elif args.cmd == "headers":
            print(pentest.http_headers(args.host, args.port, args.https))

    elif args.domain == "resolve":
        from locagents import video_resolve
        from locagents.resolve_mcp import call_resolve_tool, describe_resolve_tool, list_resolve_tools
        if args.cmd == "chat":
            video_resolve.build_agent().chat()
        elif args.cmd == "list-tools":
            print(list_resolve_tools())
        elif args.cmd == "describe":
            print(describe_resolve_tool(args.name))
        elif args.cmd == "call":
            print(call_resolve_tool(args.name, args.args_json))

    elif args.domain == "subtitles":
        from locagents.subtitles import translate_srt
        print(translate_srt(args.srt, args.lang))


if __name__ == "__main__":
    sys.exit(main())
