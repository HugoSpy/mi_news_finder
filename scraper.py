"""
scraper.py — Récupération des articles via flux RSS et pages web.
"""

import feedparser
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
import time
import re


@dataclass
class Article:
    title: str
    url: str
    source: str
    published: datetime
    content: str = ""
    summary: str = ""

    def to_dict(self):
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published": self.published.isoformat(),
            "content": self.content[:2000],  # Limite pour LLM
            "summary": self.summary,
        }


# ─── Configuration des sources RSS ───────────────────────────────────────────

RSS_SOURCES = {
    # ── Sources SI — Presse IT enterprise FR ──────────────────────────────
    "01net":             "https://www.01net.com/rss/",
    "Silicon.fr":        "https://www.silicon.fr/feed",
    "Le Monde Techno":   "https://www.lemonde.fr/technologies/rss_full.xml",

    # ── Sources SI — Cloud & vendors (annonces officielles) ───────────────
    "AWS News":          "https://aws.amazon.com/fr/blogs/aws/feed/",
    "Google Cloud Blog": "https://cloudblog.withgoogle.com/rss/",
    "SAP Newsroom":      "https://news.sap.com/feed/",
    "Microsoft News":    "https://news.microsoft.com/feed/",

    # ── Sources GL — Engineering, DevOps, qualité logicielle ──────────────
    "InfoQ":             "https://feed.infoq.com/",
    "The New Stack":     "https://thenewstack.io/feed/",
    "GitHub Blog":       "https://github.blog/feed/",
    "GitLab Blog":       "https://about.gitlab.com/atom.xml",
    "DevOps.com":        "https://devops.com/feed/",
    # ── Sources GL/SI supplémentaires ─────────────────────────────────────
    "Developpez.com":    "https://www.developpez.com/index/rss",
    "The Register":      "https://www.theregister.com/headlines.atom",
    "Changelog":         "https://changelog.com/feed",
}


# Jours abrégés en français (feedparser ne les parse pas nativement)
FR_DAYS = {"lun": "Mon", "mar": "Tue", "mer": "Wed", "jeu": "Thu",
           "ven": "Fri", "sam": "Sat", "dim": "Sun"}

def parse_date(entry) -> Optional[datetime]:
    """Extrait et normalise la date d'un article RSS.
    Gère les formats standards ET les dates avec jours en français."""
    # 1. Essai via pub_parsed (le plus fiable)
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                continue

    # 2. Fallback : parse manuel de la chaîne brute (ex: "mer, 18 Mar 2026 18:24:51 +0100")
    for attr in ("published", "updated", "created"):
        raw = getattr(entry, attr, None)
        if not raw:
            continue
        try:
            # Remplace le jour français par son équivalent anglais
            normalized = raw.strip()
            prefix = normalized[:3].lower()
            if prefix in FR_DAYS:
                normalized = FR_DAYS[prefix] + normalized[3:]
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(normalized).replace(tzinfo=timezone.utc)
        except Exception:
            try:
                # Dernier recours : dateutil si disponible
                from dateutil import parser as dp
                return dp.parse(raw).replace(tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def fetch_article_content(url: str, timeout: int = 10) -> str:
    """Tente de récupérer le contenu full-text d'un article."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            )
        }
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        # Supprime les éléments parasites
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        # Cherche le contenu principal
        for selector in ["article", "main", ".article-content", ".post-content", ".entry-content"]:
            block = soup.select_one(selector)
            if block:
                text = block.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text)
                return text[:3000]
        # Fallback : tout le body
        body = soup.body
        if body:
            text = body.get_text(separator=" ", strip=True)
            return re.sub(r"\s+", " ", text)[:3000]
    except Exception:
        pass
    return ""


def scrape_rss_source(
    name: str,
    url: str,
    start_date: datetime,
    end_date: datetime,
    fetch_content: bool = True,
    delay: float = 0.5,
) -> list[Article]:
    """Scrape un flux RSS et retourne les articles dans la plage de dates."""
    articles = []

    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"  ⚠️  Erreur RSS {name}: {e}")
        return []

    for entry in feed.entries:
        pub_date = parse_date(entry)
        if pub_date is None:
            continue

        # Filtre par date
        pub_naive = pub_date.replace(tzinfo=None) if pub_date.tzinfo else pub_date
        start_naive = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
        end_naive = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date

        if not (start_naive <= pub_naive <= end_naive):
            continue

        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
        summary = BeautifulSoup(summary, "html.parser").get_text(strip=True)[:500]

        if not title or not link:
            continue

        content = ""
        if fetch_content:
            content = fetch_article_content(link)
            time.sleep(delay)

        article = Article(
            title=title,
            url=link,
            source=name,
            published=pub_date,
            content=content or summary,
            summary=summary,
        )
        articles.append(article)

    return articles


def scrape_all(
    start_date: datetime,
    end_date: datetime,
    sources: dict = None,
    fetch_content: bool = True,
    verbose: bool = True,
) -> list[Article]:
    """Lance le scraping sur toutes les sources configurées."""
    sources = sources or RSS_SOURCES
    all_articles = []

    for name, url in sources.items():
        if verbose:
            print(f"  📡 Scraping {name}...")
        arts = scrape_rss_source(name, url, start_date, end_date, fetch_content=fetch_content)
        if verbose:
            print(f"     → {len(arts)} articles trouvés")
        all_articles.extend(arts)

    return all_articles
