#!/usr/bin/env python3
"""
main.py — CLI principal du pipeline Market Intelligence.

Usage :
    python main.py --start-date 2025-03-01 --end-date 2025-03-19
    python main.py --start-date 2025-03-01 --end-date 2025-03-19 --top-k 5
    python main.py --start-date 2025-03-01 --end-date 2025-03-19 --no-llm
    python main.py --start-date 2025-03-01 --end-date 2025-03-19 --output results.json
    python main.py --start-date 2025-03-01 --end-date 2025-03-19 --no-fetch  (RSS uniquement, sans charger les pages)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Ajoute le dossier src au path
sys.path.insert(0, str(Path(__file__).parent))

from scraper import scrape_all, RSS_SOURCES
from processor import prefilter, deduplicate
from llm_client import ClaudeClient, fallback_classify, ClassificationResult
from processor import SI_KEYWORDS, GL_KEYWORDS
from ranking import rank_and_select, format_terminal_output, to_json_output


def parse_date(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Format de date invalide : '{s}'. Attendu : YYYY-MM-DD")


def main():
    parser = argparse.ArgumentParser(
        description="Market Intelligence — Scraping IT B2B avec classification LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python main.py --start-date 2025-03-01 --end-date 2025-03-19
  python main.py --start-date 2025-03-01 --end-date 2025-03-19 --top-k 5 --output results.json
  python main.py --start-date 2025-03-01 --end-date 2025-03-19 --no-llm
        """,
    )
    parser.add_argument(
        "--start-date", required=True, type=parse_date,
        help="Date de début (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date", required=True, type=parse_date,
        help="Date de fin (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--top-k", type=int, default=3,
        help="Nombre d'articles à sélectionner par catégorie (défaut : 3)",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Utiliser uniquement les règles locales (sans appel API)",
    )
    parser.add_argument(
        "--no-fetch", action="store_true",
        help="Ne pas charger le contenu des pages, utiliser uniquement le résumé RSS",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Chemin de sortie JSON optionnel (ex : results.json)",
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="Clé API Anthropic (sinon lu depuis ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--model", type=str, default="claude-haiku-4-5",
        help="Modèle Claude à utiliser (défaut : claude-haiku-4-5)",
    )

    args = parser.parse_args()

    # ── Validation dates ──────────────────────────────────────────────────────
    if args.start_date > args.end_date:
        print("❌ Erreur : --start-date doit être antérieure à --end-date")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║           MARKET INTELLIGENCE — Pipeline B2B IT                      ║
╚══════════════════════════════════════════════════════════════════════╝
  Période    : {args.start_date.strftime('%d/%m/%Y')} → {args.end_date.strftime('%d/%m/%Y')}
  Top K      : {args.top_k} articles par catégorie
  Mode LLM   : {'❌ désactivé (règles locales)' if args.no_llm else '✅ Claude API'}
  Fetch pages: {'❌ désactivé' if args.no_fetch else '✅ activé'}
""")

    # ── Étape 1 : Scraping ────────────────────────────────────────────────────
    print("─" * 70)
    print("[ 1/5 ] 📡 SCRAPING DES SOURCES RSS")
    print("─" * 70)

    articles = scrape_all(
        start_date=args.start_date,
        end_date=args.end_date,
        fetch_content=not args.no_fetch,
        verbose=True,
    )
    print(f"\n  ✅ Total brut : {len(articles)} articles collectés")

    if not articles:
        print("\n  ⚠️  Aucun article trouvé pour cette période. Essayez d'élargir les dates.")
        sys.exit(0)

    # ── Étape 2 : Dédoublonnage ───────────────────────────────────────────────
    articles = deduplicate(articles)
    print(f"  ✅ Après dédoublonnage : {len(articles)} articles uniques")

    # ── Étape 3 : Pré-filtrage léger (sans LLM) ───────────────────────────────
    print("\n" + "─" * 70)
    print("[ 2/5 ] 🔍 PRÉ-FILTRAGE RÈGLES (sans LLM)")
    print("─" * 70)

    candidates = prefilter(articles, min_score=1, verbose=True)

    if not candidates:
        print("\n  ⚠️  Aucun candidat après pré-filtrage.")
        sys.exit(0)

    # ── Étape 4 : Classification LLM (ou fallback) ────────────────────────────
    print("\n" + "─" * 70)
    print(f"[ 3/5 ] 🤖 CLASSIFICATION {'(RÈGLES LOCALES)' if args.no_llm else '(CLAUDE API)'}")
    print("─" * 70)

    classified = []

    if args.no_llm:
        print(f"  Mode fallback : classification par mots-clés pour {len(candidates)} articles\n")
        for art in candidates:
            res = fallback_classify(art, SI_KEYWORDS, GL_KEYWORDS)
            classified.append((art, res))
    else:
        # Initialisation du client Claude
        api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("  ❌ Clé API manquante !")
            print("  → Définissez ANTHROPIC_API_KEY ou utilisez --api-key <clé>")
            print("  → Ou utilisez --no-llm pour le mode sans API\n")
            sys.exit(1)

        client = ClaudeClient(api_key=api_key, model=args.model)
        print(f"  Modèle : {args.model}")
        print(f"  Articles à classifier : {len(candidates)}\n")

        classified = client.classify_batch(candidates, verbose=True)

    # ── Étape 5 : Ranking & sélection top K ──────────────────────────────────
    print("\n" + "─" * 70)
    print(f"[ 4/5 ] 🏆 RANKING — TOP {args.top_k} SI + TOP {args.top_k} GL")
    print("─" * 70)

    ranked = rank_and_select(classified, top_k=args.top_k)

    total_si = len(ranked["SI"])
    total_gl = len(ranked["GL"])
    print(f"\n  Articles SI retenus : {total_si}")
    print(f"  Articles GL retenus : {total_gl}")

    # ── Étape 6 : Affichage final ─────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("[ 5/5 ] 📋 RÉSULTATS FINAUX")
    print("─" * 70)

    stats = None
    if not args.no_llm and 'client' in locals():
        stats = client.cost_estimate()

    output_str = format_terminal_output(
        ranked,
        start_date=args.start_date,
        end_date=args.end_date,
        stats=stats,
    )
    print(output_str)

    # ── Sauvegarde JSON optionnelle ───────────────────────────────────────────
    if args.output:
        json_data = to_json_output(ranked, stats=stats)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"  💾 Résultats sauvegardés : {output_path.resolve()}")


if __name__ == "__main__":
    main()
