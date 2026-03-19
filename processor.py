"""
processor.py — Nettoyage et pré-filtrage léger AVANT l'appel LLM.
Objectif : réduire au max le nombre d'articles envoyés au LLM → économie de coût.
"""

import re
from scraper import Article

# ─── Mots-clés B2C → exclusion stricte ──────────────────────────────────────
B2C_KEYWORDS = [
    "iphone", "samsung galaxy", "pixel ", "airpods", "ipad", "macbook",
    "apple watch", "samsung watch", "galaxy watch",
    "playstation", "xbox", "nintendo", "console de jeu",
    "smartphone grand public", "tablette grand public",
    "meilleur téléphone", "test du ", "avis sur ", "bon plan",
    "soldes", "promo", "réduction", "code promo",
    "voiture électrique grand public", "borne de recharge domicile",
    "application mobile grand public", "jeu vidéo",
    "montre connectée", "bracelet connecté",
    "casque audio", "écouteurs",
    "netflix", "disney+", "amazon prime video", "streaming vidéo",
    "réseau social", "tiktok", "instagram", "snapchat",
]

# ─── Mots-clés SI → score positif ────────────────────────────────────────────
SI_KEYWORDS = [
    "cloud", "saas", "paas", "iaas", "infrastructure",
    "erp", "crm", "sap", "oracle", "salesforce", "servicenow",
    "cybersécurité", "sécurité informatique", "ransomware", "zero trust",
    "transformation numérique", "transformation digitale",
    "data center", "datacenter", "hyperscaler",
    "migration cloud", "hybride", "multicloud",
    "dsi", "cio", "direction informatique", "si entreprise",
    "gouvernance", "conformité", "rgpd", "iso 27001",
    "architecture", "microservices", "api management",
    "big data", "data lake", "data warehouse", "analytics",
    "ia générative entreprise", "llm entreprise", "copilot entreprise",
    "microsoft azure", "aws enterprise", "google cloud enterprise",
    "ibm", "hpe", "dell", "vmware", "nutanix",
    "edge computing", "iot entreprise", "5g entreprise",
]

# ─── Mots-clés GL → score positif ────────────────────────────────────────────
GL_KEYWORDS = [
    "devops", "devsecops", "ci/cd", "pipeline", "déploiement continu",
    "intégration continue", "github actions", "gitlab", "jenkins",
    "kubernetes", "docker", "conteneur", "container", "orchestration",
    "plateforme ingénierie", "platform engineering", "idp",
    "shift left", "quality engineering", "sre", "observabilité",
    "dette technique", "refactoring", "clean code",
    "test automatisé", "test unitaire", "tdd", "bdd",
    "opentelemetry", "prometheus", "grafana",
    "low code", "no code", "développement logiciel",
    "api", "sdk", "open source entreprise",
    "developer experience", "dx", "inner source",
    "supply chain logicielle", "sbom", "sécurité applicative",
]


def normalize(text: str) -> str:
    """Normalise le texte pour la recherche par mots-clés."""
    return text.lower().replace("-", " ").replace("_", " ")


def is_b2c(article: Article) -> bool:
    """Retourne True si l'article est clairement B2C → à rejeter."""
    text = normalize(f"{article.title} {article.summary}")
    return any(kw in text for kw in B2C_KEYWORDS)


def keyword_score(article: Article, keywords: list[str]) -> int:
    """Compte le nombre de mots-clés présents dans titre + résumé."""
    text = normalize(f"{article.title} {article.summary} {article.content[:500]}")
    return sum(1 for kw in keywords if kw in text)


def prefilter(articles: list[Article], min_score: int = 1, verbose: bool = True) -> list[Article]:
    """
    Pré-filtre sans LLM :
    1. Élimine les articles B2C évidents
    2. Garde uniquement ceux avec au moins 1 mot-clé SI ou GL
    Retourne les articles candidats pour le LLM.
    """
    candidates = []
    rejected_b2c = 0
    rejected_irrelevant = 0

    for art in articles:
        # Exclusion B2C stricte
        if is_b2c(art):
            rejected_b2c += 1
            continue

        # Score SI + GL combiné
        si_score = keyword_score(art, SI_KEYWORDS)
        gl_score = keyword_score(art, GL_KEYWORDS)

        if si_score + gl_score < min_score:
            rejected_irrelevant += 1
            continue

        candidates.append(art)

    if verbose:
        print(f"\n  🔍 Pré-filtrage :")
        print(f"     Total brut       : {len(articles)}")
        print(f"     Rejetés B2C      : {rejected_b2c}")
        print(f"     Hors sujet       : {rejected_irrelevant}")
        print(f"     Candidats LLM    : {len(candidates)}")

    return candidates


def deduplicate(articles: list[Article]) -> list[Article]:
    """Supprime les doublons par URL et titre similaire."""
    seen_urls = set()
    seen_titles = set()
    unique = []

    for art in articles:
        # Normalise le titre pour comparaison
        title_key = re.sub(r"[^a-z0-9]", "", normalize(art.title))[:60]

        if art.url in seen_urls:
            continue
        if title_key in seen_titles:
            continue

        seen_urls.add(art.url)
        seen_titles.add(title_key)
        unique.append(art)

    return unique
