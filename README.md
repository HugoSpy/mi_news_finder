# Market Intelligence — Pipeline B2B IT

Outil de scraping et classification automatique de news IT enterprise.  
Sélectionne les **3 meilleures news SI** et les **3 meilleures news GL** sur une période donnée.

---

## Deux modes de fonctionnement

### 🤖 Mode LLM (recommandé)

Utilise l'API Claude pour classifier, scorer et justifier chaque article.  
**Coût : ~20-30 centimes max par exécution.** Résultats de qualité, justifications détaillées.

```bash
python main.py --start-date 2026-03-01 --end-date 2026-03-19
```

### 🆓 Mode gratuit (`--no-llm`)

Pas d'API, classification par mots-clés uniquement.  
**Gratuit, mais moins précis** — sélectionne par comptage de mots-clés, pas par pertinence réelle.  
Utile pour tester que le scraping fonctionne, pas pour une présentation.

```bash
python main.py --start-date 2026-03-01 --end-date 2026-03-19 --no-llm
```

---

## Structure du projet

```
mi_news_finder/
├── main.py          # CLI principal — point d'entrée
├── scraper.py       # Récupération RSS + contenu full-text
├── processor.py     # Pré-filtrage B2C + scoring mots-clés
├── llm_client.py    # Appel API Claude + fallback local
├── ranking.py       # Tri, sélection top K, affichage
├── requirements.txt
├── .env.example
└── README.md
```

---

## Installation

```bash
cd mi_news_finder
python -m venv venv
source venv/bin/activate        # Linux/Mac
# ou : venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

---

## Configuration de la clé API

Nécessaire uniquement pour le mode LLM. Clé disponible sur https://console.anthropic.com/

```bash
# Linux / Mac / WSL
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxx"

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-xxxxxxxxxxxx"

# Ou directement dans la commande
python main.py --api-key sk-ant-xxxx ...
```

---

## Toutes les options CLI

```bash
python main.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD [options]

Options :
  --top-k N        Nombre d'articles par catégorie (défaut : 3)
  --no-llm         Mode gratuit, sans API
  --no-fetch       Ne pas charger le contenu des pages (plus rapide)
  --output FILE    Sauvegarder les résultats en JSON
  --api-key KEY    Clé API Anthropic (sinon lu depuis ANTHROPIC_API_KEY)
  --model MODEL    Modèle Claude (défaut : claude-haiku-4-5-20251001)
```

---

## Sources configurées

| Source            | Catégorie                 |
| ----------------- | ------------------------- |
| 01net             | SI — Presse IT FR         |
| Silicon.fr        | SI — Presse IT FR         |
| Le Monde Techno   | SI — Presse IT FR         |
| AWS News          | SI — Vendor cloud         |
| Google Cloud Blog | SI — Vendor cloud         |
| SAP Newsroom      | SI — Vendor ERP           |
| Microsoft News    | SI — Vendor               |
| InfoQ             | GL — Engineering          |
| The New Stack     | GL — Cloud-native         |
| GitHub Blog       | GL — DevOps               |
| GitLab Blog       | GL — DevSecOps            |
| DevOps.com        | GL — Pratiques            |
| The Register      | GL/SI — Actualité tech EN |
| Developpez.com    | GL — Dev FR               |
| Changelog         | GL — Releases open source |

---

## Pipeline de traitement

```
RSS Sources → Scraping → Déduplication → Pré-filtrage mots-clés (gratuit)
                                                    ↓
                              B2C détecté → REJET immédiat (sans LLM)
                                                    ↓
                              Candidats → Appel Claude API (mode LLM)
                                       ou score mots-clés (mode --no-llm)
                                                    ↓
                              Classification SI/GL + Score + Justification
                                                    ↓
                              Ranking → Top 3 SI + Top 3 GL → Affichage
```

---

## Définitions métier

**SI — Systèmes d'Information** : cloud enterprise, infrastructure IT, ERP/CRM, cybersécurité, data/BI, architecture SI, gouvernance, transformation numérique, souveraineté numérique, conformité réglementaire (NIS2, DORA, AI Act).

**GL — Génie Logiciel** : DevOps, CI/CD, testing, qualité logicielle, platform engineering, conteneurs/Kubernetes, observabilité, developer experience, sécurité applicative, releases majeures de langages/outils enterprise.

**REJECT** : B2C (smartphones, gadgets, consoles), tutos vendor, articles anniversaire sans annonce, people news.

---

## Estimation des coûts API

Modèle utilisé : `claude-haiku-4-5-20251001`

| Scénario                      | Articles scrapés | Candidats LLM | Coût estimé |
| ----------------------------- | ---------------- | ------------- | ----------- |
| 3 semaines (usage typique MI) | ~200             | ~120          | ~$0.25      |
| 1 mois                        | ~300             | ~160          | ~$0.30      |
| Test `--no-fetch` rapide      | ~200             | ~120          | ~$0.15      |
