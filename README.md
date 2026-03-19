# Market Intelligence — Pipeline B2B IT

Outil de scraping et classification automatique de news IT enterprise.  
Sélectionne les **3 meilleures news SI** et les **3 meilleures news GL** sur une période donnée, avec classification via l'API Claude (Anthropic).

---

## Structure du projet

```
market-intel/
├── src/
│   ├── main.py          # CLI principal — point d'entrée
│   ├── scraper.py       # Récupération RSS + contenu full-text
│   ├── processor.py     # Pré-filtrage B2C + scoring mots-clés
│   ├── llm_client.py    # Appel API Claude + fallback local
│   └── ranking.py       # Tri, sélection top K, affichage
├── requirements.txt
└── README.md
```

---

## Installation

```bash
# Cloner ou dézipper le projet
cd market-intel

# Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate        # Linux/Mac
# ou : venv\Scripts\activate    # Windows

# Installer les dépendances
pip install -r requirements.txt
```

---

## Configuration de la clé API

```bash
# Linux / Mac
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxx"

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-xxxxxxxxxxxx"

# Ou directement dans la commande :
python src/main.py --api-key sk-ant-xxxx ...
```

La clé API Anthropic est disponible sur : https://console.anthropic.com/

---

## Utilisation

### Commande de base

```bash
python src/main.py --start-date 2025-03-01 --end-date 2025-03-19
```

### Avec plus d'options

```bash
# Top 5 au lieu de top 3
python src/main.py --start-date 2025-03-01 --end-date 2025-03-19 --top-k 5

# Sauvegarder les résultats en JSON
python src/main.py --start-date 2025-03-01 --end-date 2025-03-19 --output output/results.json

# Mode sans LLM (règles locales uniquement, gratuit)
python src/main.py --start-date 2025-03-01 --end-date 2025-03-19 --no-llm

# Mode rapide (pas de chargement des pages, RSS seulement)
python src/main.py --start-date 2025-03-01 --end-date 2025-03-19 --no-fetch
```

---

## Pipeline de traitement

```
RSS Sources → Scraping → Déduplication → Pré-filtrage (règles)
                                                    ↓
                              B2C détecté → REJET immédiat (sans LLM)
                                                    ↓
                              Candidats SI/GL → Appel Claude API
                                                    ↓
                              Classification + Score + Justification
                                                    ↓
                              Ranking → Top 3 SI + Top 3 GL → Affichage
```

**Stratégie hybride :**  
Les règles locales (mots-clés B2C, SI, GL) filtrent ~60-70% des articles avant tout appel LLM.  
Le LLM ne traite que les articles candidats pertinents → coût API minimal.

---

## Sources configurées

| Source | Type |
|---|---|
| 01net | Actualité IT FR |
| ZDNet FR | Actualité IT FR |
| Silicon.fr | IT Enterprise FR |
| Les Échos Tech | Business/Tech |
| Le Monde Techno | Généraliste tech |
| IBM Blog | Vendor |
| SAP Blog | Vendor ERP |
| AWS News | Cloud |
| Google Cloud Blog | Cloud |
| Microsoft Tech Community | Cloud/Enterprise |

Pour ajouter une source : éditer `RSS_SOURCES` dans `src/scraper.py`.

---

## Définitions métier

### SI — Systèmes d'Information
Cloud, infrastructure IT, ERP, CRM, cybersécurité, data/BI, architecture SI, gouvernance IT, transformation numérique enterprise, migrations, hyperscalers en contexte enterprise.

### GL — Génie Logiciel
DevOps, CI/CD, testing, qualité logicielle, platform engineering, conteneurs/Kubernetes, observabilité, developer experience, sécurité applicative, industrialisation logicielle.

### REJECT
Tout contenu B2C (smartphones, gadgets, consoles), people/rumeurs, hors IT enterprise.

---

## Estimation des coûts API

Avec le modèle `claude-haiku-4-5` (recommandé) :

| Scénario | Articles scrapés | Candidats LLM | Coût estimé |
|---|---|---|---|
| 1 semaine | ~200 | ~40 | ~$0.005 |
| 1 mois | ~800 | ~150 | ~$0.02 |
| Test rapide | ~50 | ~10 | < $0.001 |

---

## Exemple de sortie terminal

```
══════════════════════════════════════════════════════════════════════
  📊  MARKET INTELLIGENCE — RÉSULTATS
  Période : 01/03/2025 → 19/03/2025
══════════════════════════════════════════════════════════════════════

  🔵  TOP 3 — SYSTÈMES D'INFORMATION
  ──────────────────────────────────────────────────────────────────

  #1  [92/100]  SAP annonce une migration massive vers RISE with SAP pour 500 clients
      📰  Source   : SAP Blog
      📅  Date     : 15/03/2025
      🔗  URL      : https://...
      📝  Résumé   : SAP accélère la migration cloud de ses clients ERP via une offre packagée.
      💡  Pourquoi : Impact direct sur les DSI de grands groupes utilisant SAP. Concerne la
                     transformation SI de milliers d'entreprises françaises.

  ...

  🟢  TOP 3 — GÉNIE LOGICIEL
  ──────────────────────────────────────────────────────────────────

  #1  [88/100]  GitHub Actions introduit des runners ARM natifs pour CI/CD enterprise
      ...
```
