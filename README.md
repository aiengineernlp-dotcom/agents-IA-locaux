# Agents IA locaux — SEO · ML/IA · Vidéo

Setup **100 % gratuit et local** (Ollama + Python) pour un Mac Pro 2020. Trois agents spécialisés, utilisables en ligne de commande **et** depuis une interface web (Open WebUI).

```
                 ┌──────────────── Open WebUI (optionnel) ────────────────┐
                 │  6 agents (chat, sans outils) : seo · ml · video ·      │
                 │  sast · forensics · pentest                            │
                 └───────────────────────────┬────────────────────────────┘
                                             │
   python run.py … ──►  locagents/agent.py ──┼──►  Ollama (modèles locaux)
      (agents AVEC outils)                   │
        ├─ seo.py        audit_page · crawl_site · serp_snapshot · cluster_keywords
        ├─ ml.py          list_files · read_file · write_file · run_python (bac à sable)
        ├─ video.py      create_video_script · render_video · list_outputs
        ├─ sast.py        scan_secrets · scan_code_patterns · scan_python_security · scan_dependencies · full_audit
        ├─ forensics.py  analyze_auth_log · analyze_web_log · search_iocs · generate_sigma_rule
        └─ pentest.py    check_scope · port_scan · vuln_scan · grab_banner · http_headers
                              ↑ toute action réseau passe par scope.py (liste blanche obligatoire)
```

## Contenu

| Fichier | Rôle |
|---|---|
| `install.sh` | Installation reproductible en une commande |
| `.env.example` | Choix des modèles, contexte, voix (copié en `.env`) |
| `requirements.txt` | Dépendances Python |
| `prompts/*.md` | **Personnalité de chaque agent** — le fichier à modifier pour le faire évoluer |
| `scripts/create_ollama_agents.py` | Crée `agent-seo`, `agent-ml`, `agent-video` dans Ollama (générés dans `models/`) |
| `locagents/` | Le code : framework d'agent (`agent.py`) + un module par agent |
| `run.py` | Point d'entrée unique en ligne de commande |
| `docker-compose.yml` | Open WebUI (interface type ChatGPT) |
| `outputs/` | Tout ce que produisent les agents (CSV, vidéos, sous-titres) |
| `workspace/` | Bac à sable de l'agent ML |
| `scope/pentest_scope.yml` | Liste blanche des cibles autorisées pour l'agent pentest |
| `scripts/setup_resolve_bridge.sh` | Installe le pont DaVinci Resolve (agent `resolve`) |
| `third_party/` | Dépôts externes clonés par les scripts d'installation (ignoré par git) |

## Installation

Prérequis : Homebrew, [Ollama](https://ollama.com/download), et (optionnel) Docker Desktop.

```bash
cd agents-locaux
./install.sh
```

Le script installe FFmpeg, crée `.venv`, télécharge les modèles, crée les 3 agents et lance un diagnostic. Relançable sans risque. Vérification à tout moment : `python run.py doctor`.

## Utilisation

```bash
source .venv/bin/activate

# SEO
python run.py seo chat
python run.py seo audit https://exemple.com
python run.py seo crawl https://exemple.com --max 30      # → outputs/seo_crawl_*.csv
python run.py seo serp "chaussures de trail"
python run.py seo cluster mots_cles.csv --k 10            # colonne "keyword" → outputs/seo_clusters.csv

# ML / IA
python run.py ml chat
python run.py ml task "Entraîne un RandomForest sur le dataset iris, affiche l'accuracy en validation croisée"

# Vidéo
python run.py video make "Comment fonctionne le clustering sémantique" --scenes 5
python run.py video chat                                  # ou en langage naturel
python run.py video render outputs/<dossier>/scenes.json  # re-rendre après avoir édité le JSON

# SAST (audit de code)
python run.py sast audit ~/code/mon-projet                # rapport complet → outputs/sast_*.md
python run.py sast secrets ~/code/mon-projet               # gitleaks seul
python run.py sast chat

# Forensics / analyse de logs (aucune action réseau, juste des fichiers)
python run.py forensics auth /var/log/auth.log
python run.py forensics web /var/log/nginx/access.log
python run.py forensics ioc mon.log "1.2.3.4, evil.example.com"
python run.py forensics chat

# Pentest (lab isolé, périmètre obligatoire — voir plus bas)
python run.py pentest scope                                # affiche le périmètre autorisé
python run.py pentest check 192.168.56.10                  # vérifie sans rien lancer
python run.py pentest scan 192.168.56.10 --ports 1-1000
python run.py pentest vuln 192.168.56.10
python run.py pentest chat
```

Le pipeline vidéo : le LLM écrit un JSON de scènes (sortie contrainte par schéma, donc fiable même avec un 7B) → diapositives Pillow → voix macOS `say` → montage MoviePy/FFmpeg → `video.mp4` + `video.srt`. Tu peux éditer `scenes.json` à la main avant de relancer `render`.

## Interface graphique (Open WebUI)

```bash
docker compose up -d      # puis http://localhost:3000
```

Les trois modèles `agent-seo`, `agent-ml`, `agent-video` apparaissent dans le sélecteur de modèles. Attention : dans Open WebUI ils **discutent** avec le prompt de l'agent mais n'exécutent pas les outils (audit, crawl, rendu vidéo…) ; pour ça, utilise `run.py`. Alternative sans Docker : `python3.11 -m venv ow && ow/bin/pip install open-webui && ow/bin/open-webui serve`.

## Pilier Hacking / SecOps — périmètre obligatoire

Trois agents distincts, avec des règles différentes :

- **`sast`** — audit statique de code (secrets, injections, crypto faible, dépendances vulnérables). Aucune restriction réseau : c'est du code local. Outils : gitleaks, semgrep, bandit, pip-audit.
- **`forensics`** — analyse de logs et recherche d'IOC déjà sur ton disque. Aucune action réseau non plus. Génère des règles Sigma exportables vers un SIEM.
- **`pentest`** — le seul agent qui touche au réseau. **Toute cible doit être déclarée dans `scope/pentest_scope.yml`** (IP, CIDR ou hostname) avant d'être scannée : `port_scan`, `vuln_scan`, `grab_banner` et `http_headers` appellent tous `scope.require_in_scope()` en premier et lèvent une exception sinon — ce n'est pas une simple recommandation dans le prompt, c'est vérifié en code avant l'exécution. Édite ce fichier toi-même pour chaque nouvelle cible ; n'y mets que des machines que tu possèdes ou pour lesquelles tu as une autorisation écrite explicite (VM de lab, range CTF, environnement de test interne déclaré). Il ne fait que de la reconnaissance (scan de ports/services, bannières, en-têtes HTTP) — volontairement pas d'exploitation automatisée.

Pour un vrai lab isolé (recommandé avant tout test actif) : une VM Kali via UTM (gratuit, natif Apple Silicon/Intel) ou un conteneur Docker `kalilinux/kali-rolling`, sur un réseau interne dédié (ex. le CIDR `192.168.56.0/24` déjà dans `scope/pentest_scope.yml`) — pas sur ton réseau Wi-Fi principal.

## Montage vidéo piloté (DaVinci Resolve)

Un 7e agent, `resolve`, pilote **DaVinci Resolve** pour du montage — timelines, marqueurs, mix audio, correspondance de couleurs, rendu — via le pont communautaire [`unofficial-davinci-mcp`](https://github.com/wassermanproductions/unofficial-davinci-mcp).

**Important, découvert en pratique** : DaVinci Resolve **Free** a verrouillé le scripting interne (Workspace → Scripts → Python) sur les versions récentes — un premier pont testé (`CursorBridge`, qui tournait *dans* Resolve) s'est heurté à ce blocage. Ce pont-ci le contourne : il tourne comme un **processus externe indépendant** et détecte automatiquement deux modes, sans jamais dépendre du scripting bloqué :

| | Resolve **Studio** (payant) | Resolve **Free** (gratuit) |
|---|---|---|
| Timelines, rendu | Pilotage direct dans l'app | Génère un fichier **FCPXML** → `File → Import → Timeline` |
| Marqueurs | Insérés en direct | Fichier CSV de marqueurs |
| LUT / étalonnage | Appliqué par l'API | Fichier `.cube` à glisser sur un node |
| Analyse (probe, beat-matching, tightening dialogue, loudness) | ✅ dans les deux cas | ✅ dans les deux cas |

L'outil `resolve_capabilities` dit dans quel mode tu es et pourquoi — l'agent l'appelle toujours en premier.

### Installation

```bash
brew install --cask davinci-resolve      # ou télécharge depuis blackmagicdesign.com (Free)
./scripts/setup_resolve_bridge.sh        # pip install du pont, aucune manipulation dans Resolve
```

Contrairement à la première tentative, **rien à faire dans l'interface de Resolve** (pas de Workspace → Scripts) : le pont est un simple paquet Python.

```bash
source .venv/bin/activate
python run.py resolve call resolve_capabilities '{}'   # confirme le mode (live / interchange) avant tout
python run.py resolve list-tools                       # 23 outils (probe, beat_grid, generate_fcpxml, resolve_render…)
python run.py resolve call generate_fcpxml '{"name": "Mon montage", "clips": [...], "dry_run": false}'
python run.py resolve chat                              # langage naturel
```

### Comment ça marche

```
run.py resolve ──► locagents/video_resolve.py ──► locagents/resolve_mcp.py (client MCP, stdio)
                                                          │
                                                          ▼
                                    unofficial-davinci-mcp (processus Python externe, pip installé)
                                                          │
                                          ┌───────────────┴───────────────┐
                                          ▼                               ▼
                                 mode "live" (Studio ouvert)     mode "interchange" (Free)
                                 pilote l'app via l'API           écrit FCPXML/EDL/CSV
                                 officielle de scripting          à importer à la main
```

L'agent ne connaît pas à l'avance tous les noms d'outils exacts : il commence par `list_resolve_tools`, vérifie les arguments avec `describe_resolve_tool` si besoin, puis appelle `call_resolve_tool`. Presque tous les outils qui modifient quelque chose acceptent `dry_run` (true par défaut, prévisualise seulement) et `confirm` (à passer à true avec `dry_run=false` pour appliquer réellement) — l'agent prévisualise toujours avant d'appliquer.

En mode interchange (Free), l'agent prépare tout le montage (coupes calées sur le rythme, dialogue resserré, mixage, LUT) sous forme de fichiers, et te dit précisément quoi importer dans Resolve. Pas de pilotage en temps réel, mais un vrai gain de temps sur la préparation.

### Connexion directe à Claude (hors ligne de commande)

Ce pont est un serveur MCP standard (stdio) : il peut aussi se connecter directement à **Claude Desktop** (Réglages → Connecteurs → ajouter un serveur MCP local, commande `unofficial-davinci-mcp`) pour piloter Resolve en discutant avec Claude sans repasser par `run.py`. Ce n'est pas possible depuis une conversation web/mobile classique comme celle-ci — seul Claude Desktop sait se connecter à des serveurs MCP tournant sur ta machine.

## À savoir sur ton matériel

- **Mac Intel = probablement CPU uniquement.** À ma connaissance Ollama n'exploite pas les GPU AMD du Mac Pro 2020 sous macOS. Vérifie : lance un prompt, puis `ollama ps` → colonne PROCESSOR. Si c'est `100% CPU`, la VRAM ne sert pas et la RAM/les cœurs Xeon font tout le travail.
- C'est pourquoi les modèles par défaut sont des **7B** (quelques tokens/s sur CPU, correct). Les 14B (`qwen2.5:14b`, `qwen2.5-coder:14b`) tiennent largement dans ta RAM mais seront plus lents : change-les dans `.env`, relance `./install.sh`.
- `deepseek-r1` ne supporte pas les outils : l'agent bascule automatiquement en mode texte seul (utile pour raisonner, pas pour exécuter du code).
- Les entraînements PyTorch lourds resteront lents sans CUDA ; l'agent ML est surtout un assistant de code et de débogage.

## Sécurité et limites

- L'agent ML **exécute le code qu'il écrit** (`run_python`), confiné au dossier `workspace/` pour les fichiers mais pas isolé du système. Ne lui donne pas de consigne dont tu ne voudrais pas voir le résultat.
- `crawl_site` respecte `robots.txt` et temporise 0,5 s entre pages. `serp_snapshot` (DuckDuckGo HTML) est fragile et à usage modéré ; il n'y a pas de volumes de recherche ni de backlinks sans API payante.
- Les petits modèles se trompent parfois d'outil ou d'argument : reformule, ou utilise directement les sous-commandes déterministes (`audit`, `crawl`, `cluster`, `make`), qui ne dépendent pas du LLM pour l'exécution.

## Ajouter un agent

1. `prompts/mon_agent.md` : le prompt système.
2. `locagents/mon_agent.py` : tes fonctions Python (avec docstring `Args:` — elle devient le schéma de l'outil) et `build_agent()`.
3. Une entrée dans `run.py` et dans `AGENTS` de `scripts/create_ollama_agents.py`.

## Passer à CrewAI plus tard

Le framework maison évite une dépendance lourde et fragile entre versions. Tes fonctions d'outils (`audit_page`, `cluster_keywords`…) sont de simples fonctions Python : elles se réutilisent telles quelles dans CrewAI/LangGraph si tu veux des équipes multi-agents.
