"""Agent SEO : audit on-page, crawl, aperçu SERP, clustering sémantique — 100 % local."""
from __future__ import annotations

import csv
import re
import time
from collections import deque
from urllib import robotparser
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import config
from .agent import Agent, client

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 LocalSEOAgent/1.0"
    )
}


def _get(url: str, timeout: int = 15):
    t0 = time.time()
    r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    return r, round(time.time() - t0, 2)


# ----------------------------------------------------------------------
def audit_page(url: str) -> dict:
    """Audit SEO on-page d'une URL : title, meta description, Hn, mots, images sans alt, liens, balises techniques, problèmes détectés.

    Args:
        url: L'adresse complète de la page à auditer (https://...).
    """
    r, secs = _get(url)
    return _audit_response(r, secs)


def _audit_response(r, secs: float) -> dict:
    soup = BeautifulSoup(r.text, "lxml")

    title = soup.title.get_text(strip=True) if soup.title else ""
    md = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    desc = (md.get("content") or "").strip() if md else ""
    rb = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    robots = (rb.get("content") or "").lower() if rb else ""
    canon = soup.find("link", rel="canonical")
    canonical = canon.get("href") if canon else None
    has_schema = bool(soup.find("script", attrs={"type": "application/ld+json"}))
    has_og = bool(soup.find("meta", attrs={"property": "og:title"}))
    has_viewport = bool(soup.find("meta", attrs={"name": "viewport"}))
    lang = soup.html.get("lang") if soup.html else None

    headings = {f"h{i}": [h.get_text(" ", strip=True) for h in soup.find_all(f"h{i}")] for i in (1, 2, 3)}
    imgs = soup.find_all("img")
    no_alt = [i.get("src", "")[:80] for i in imgs if not (i.get("alt") or "").strip()]

    host = urlparse(r.url).netloc
    internal = external = 0
    for a in soup.find_all("a", href=True):
        full = urljoin(r.url, a["href"])
        if not full.startswith("http"):
            continue
        if urlparse(full).netloc == host:
            internal += 1
        else:
            external += 1

    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    words = len(soup.get_text(" ", strip=True).split())

    issues = []
    if r.status_code != 200:
        issues.append(f"Statut HTTP {r.status_code}")
    if not r.url.startswith("https"):
        issues.append("Page non HTTPS")
    if not title:
        issues.append("Title manquant")
    elif not 30 <= len(title) <= 60:
        issues.append(f"Title de {len(title)} caractères (idéal 30-60)")
    if not desc:
        issues.append("Meta description manquante")
    elif not 70 <= len(desc) <= 160:
        issues.append(f"Meta description de {len(desc)} caractères (idéal 70-160)")
    if len(headings["h1"]) != 1:
        issues.append(f"{len(headings['h1'])} balise(s) H1 (il en faut exactement 1)")
    if words < 300:
        issues.append(f"Contenu court ({words} mots)")
    if no_alt:
        issues.append(f"{len(no_alt)} image(s) sans attribut alt")
    if not canonical:
        issues.append("Balise canonical absente")
    if "noindex" in robots:
        issues.append("Page en noindex")
    if not has_viewport:
        issues.append("Meta viewport absente (mobile)")
    if secs > 2:
        issues.append(f"Réponse lente ({secs}s)")

    return {
        "url": r.url,
        "status": r.status_code,
        "response_time_s": secs,
        "title": title,
        "title_len": len(title),
        "meta_description": desc,
        "meta_description_len": len(desc),
        "canonical": canonical,
        "robots": robots or None,
        "lang": lang,
        "headings": {k: v[:10] for k, v in headings.items()},
        "word_count": words,
        "images": len(imgs),
        "images_without_alt": len(no_alt),
        "internal_links": internal,
        "external_links": external,
        "structured_data": has_schema,
        "open_graph": has_og,
        "issues": issues,
    }


def crawl_site(start_url: str, max_pages: int = 20) -> str:
    """Explore un site (même domaine, robots.txt respecté), audite chaque page et enregistre un CSV.

    Args:
        start_url: URL de départ (page d'accueil en général).
        max_pages: Nombre maximum de pages à explorer (défaut 20).
    """
    max_pages = int(max_pages)
    root = urlparse(start_url)
    rp = robotparser.RobotFileParser()
    try:
        rp.set_url(f"{root.scheme}://{root.netloc}/robots.txt")
        rp.read()
    except Exception:
        rp = None

    seen, queue, rows = set(), deque([start_url]), []
    while queue and len(rows) < max_pages:
        url = urldefrag(queue.popleft())[0]
        if url in seen:
            continue
        seen.add(url)
        if rp and not rp.can_fetch(HEADERS["User-Agent"], url):
            continue
        try:
            r, secs = _get(url)
            if "text/html" not in r.headers.get("Content-Type", ""):
                continue
            res = _audit_response(r, secs)
        except Exception as e:
            rows.append({"url": url, "status": "ERR", "issues": str(e)})
            continue
        rows.append({
            "url": res["url"], "status": res["status"], "title": res["title"],
            "title_len": res["title_len"], "meta_description_len": res["meta_description_len"],
            "h1_count": len(res["headings"]["h1"]), "word_count": res["word_count"],
            "images_without_alt": res["images_without_alt"], "internal_links": res["internal_links"],
            "response_time_s": res["response_time_s"], "issues": " | ".join(res["issues"]),
        })
        for a in BeautifulSoup(r.text, "lxml").find_all("a", href=True):
            nxt = urldefrag(urljoin(url, a["href"]))[0]
            if urlparse(nxt).netloc == root.netloc and nxt not in seen and nxt.startswith("http"):
                queue.append(nxt)
        time.sleep(0.5)  # politesse

    out = config.OUTPUTS / f"seo_crawl_{root.netloc.replace(':', '_')}.csv"
    if rows:
        keys = list({k: None for row in rows for k in row})
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    with_issues = sum(1 for r in rows if r.get("issues"))
    return f"{len(rows)} pages auditées, {with_issues} avec au moins un problème. CSV : {out}"


def serp_snapshot(query: str, n: int = 10) -> list:
    """Récupère les premiers résultats de recherche (DuckDuckGo HTML) pour une requête. Usage modéré.

    Args:
        query: La requête à rechercher.
        n: Nombre de résultats (défaut 10).
    """
    r = requests.get("https://html.duckduckgo.com/html/", params={"q": query}, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "lxml")
    results = []
    for i, a in enumerate(soup.select("a.result__a"), 1):
        href = a.get("href", "")
        if "uddg=" in href:
            href = parse_qs(urlparse(href).query).get("uddg", [href])[0]
        results.append({"rank": i, "title": a.get_text(" ", strip=True), "url": href})
        if i >= int(n):
            break
    if not results:
        return [{"info": "Aucun résultat (page de blocage possible). Réessaie plus tard ou fournis les URLs concurrentes à auditer."}]
    return results


def cluster_keywords(csv_path: str, n_clusters: int = 8, column: str = "keyword") -> str:
    """Regroupe des mots-clés par thème (embeddings Ollama, repli TF-IDF) et enregistre un CSV.

    Args:
        csv_path: Chemin du CSV contenant les mots-clés.
        n_clusters: Nombre de groupes souhaités (défaut 8).
        column: Nom de la colonne des mots-clés (défaut 'keyword'; sinon 1re colonne).
    """
    import numpy as np
    import pandas as pd
    from sklearn.cluster import KMeans

    df = pd.read_csv(csv_path)
    col = column if column in df.columns else df.columns[0]
    kws = df[col].dropna().astype(str).str.strip().drop_duplicates().tolist()
    if len(kws) < 2:
        return "Pas assez de mots-clés pour faire un clustering."
    k = max(2, min(int(n_clusters), len(kws)))

    method = "embeddings"
    try:
        vecs = []
        for i in range(0, len(kws), 128):
            vecs += client.embed(model=config.MODEL_EMBED, input=kws[i:i + 128]).embeddings
        X = np.array(vecs, dtype="float32")
        X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-9
    except Exception as e:
        print(f"⚠️  Embeddings indisponibles ({type(e).__name__}) → repli TF-IDF")
        from sklearn.feature_extraction.text import TfidfVectorizer
        X = TfidfVectorizer(ngram_range=(1, 2)).fit_transform(kws)
        method = "tf-idf"

    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    reps = km.transform(X).argmin(axis=0)  # mot-clé le plus central de chaque cluster
    labels = {c: kws[reps[c]] for c in range(k)}

    out_df = pd.DataFrame({"cluster_id": km.labels_, "keyword": kws})
    out_df["cluster_label"] = out_df["cluster_id"].map(labels)
    out_df = out_df.sort_values(["cluster_id", "keyword"])
    out = config.OUTPUTS / "seo_clusters.csv"
    out_df.to_csv(out, index=False)

    lines = [f"{len(kws)} mots-clés → {k} clusters ({method}). CSV : {out}"]
    for c, g in out_df.groupby("cluster_id"):
        lines.append(f"- [{labels[c]}] ({len(g)}) : " + ", ".join(g["keyword"].head(6)))
    return "\n".join(lines)


def build_agent() -> Agent:
    return Agent(
        name="Agent SEO",
        model=config.MODEL_GENERAL,
        system=config.load_prompt("seo"),
        tools=[audit_page, crawl_site, serp_snapshot, cluster_keywords],
    )
