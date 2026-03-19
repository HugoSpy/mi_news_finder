"""
ranking.py — Sélection et affichage du top K SI + top K GL.
"""

from dataclasses import dataclass
from scraper import Article
from llm_client import ClassificationResult


@dataclass
class RankedArticle:
    article: Article
    result: ClassificationResult

    @property
    def score(self):
        return self.result.score

    @property
    def category(self):
        return self.result.category


def rank_and_select(
    classified: list[tuple[Article, ClassificationResult]],
    top_k: int = 3,
) -> dict:
    """
    Sépare les articles classifiés en SI / GL,
    trie par score décroissant, retourne les top K de chaque catégorie.
    """
    si_articles = []
    gl_articles = []

    for art, res in classified:
        if res.category == "SI" and not res.is_b2c and res.score > 0:
            si_articles.append(RankedArticle(art, res))
        elif res.category == "GL" and not res.is_b2c and res.score > 0:
            gl_articles.append(RankedArticle(art, res))

    si_sorted = sorted(si_articles, key=lambda x: x.score, reverse=True)[:top_k]
    gl_sorted = sorted(gl_articles, key=lambda x: x.score, reverse=True)[:top_k]

    return {"SI": si_sorted, "GL": gl_sorted}


def format_terminal_output(
    ranked: dict,
    start_date,
    end_date,
    stats: dict = None,
) -> str:
    """Génère un affichage terminal propre et lisible."""

    lines = []
    sep = "═" * 70

    lines.append(f"\n{sep}")
    lines.append("  📊  MARKET INTELLIGENCE — RÉSULTATS")
    lines.append(f"  Période : {start_date.strftime('%d/%m/%Y')} → {end_date.strftime('%d/%m/%Y')}")
    lines.append(sep)

    for category, label, icon in [("SI", "SYSTÈMES D'INFORMATION", "🔵"), ("GL", "GÉNIE LOGICIEL", "🟢")]:
        articles = ranked.get(category, [])
        lines.append(f"\n  {icon}  TOP {len(articles)} — {label}")
        lines.append("  " + "─" * 66)

        if not articles:
            lines.append("  ⚠️  Aucun article trouvé dans cette catégorie.")
            continue

        for i, ranked_art in enumerate(articles, 1):
            art = ranked_art.article
            res = ranked_art.result

            lines.append(f"\n  #{i}  [{res.score}/100]  {art.title}")
            lines.append(f"      📰  Source   : {art.source}")
            lines.append(f"      📅  Date     : {art.published.strftime('%d/%m/%Y')}")
            lines.append(f"      🔗  URL      : {art.url}")
            lines.append(f"      📝  Résumé   : {res.summary}")
            lines.append(f"      💡  Pourquoi : {res.justification}")

    if stats:
        lines.append(f"\n{sep}")
        lines.append("  💰  COÛT API")
        lines.append(f"      Appels LLM     : {stats.get('calls', 0)}")
        lines.append(f"      Tokens input   : {stats.get('input_tokens', 0)}")
        lines.append(f"      Tokens output  : {stats.get('output_tokens', 0)}")
        lines.append(f"      Coût estimé    : ${stats.get('estimated_cost_usd', 0):.4f}")

    lines.append(f"\n{sep}\n")
    return "\n".join(lines)


def to_json_output(ranked: dict, stats: dict = None) -> dict:
    """Sérialise les résultats en dict JSON-compatible."""
    output = {}
    for category in ["SI", "GL"]:
        output[category] = [
            {
                "rank": i + 1,
                "score": ra.score,
                "article": ra.article.to_dict(),
                "classification": {
                    "category": ra.result.category,
                    "justification": ra.result.justification,
                    "summary": ra.result.summary,
                    "is_b2c": ra.result.is_b2c,
                },
            }
            for i, ra in enumerate(ranked.get(category, []))
        ]
    if stats:
        output["api_stats"] = stats
    return output
