"""
llm_client.py — Appel à l'API Claude (Anthropic) pour classification et scoring.
"""

import os
import json
import time
import httpx
from dataclasses import dataclass
from scraper import Article


DEFAULT_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


@dataclass
class ClassificationResult:
    category: str          # "SI" | "GL" | "REJECT"
    score: int             # 0–100
    justification: str
    is_b2c: bool
    summary: str
    raw_response: str = ""
    error: str = ""


SYSTEM_PROMPT = """Tu es un analyste senior en transformation IT des grandes entreprises (CAC40, ETI).
Ta mission : évaluer des articles de presse pour un Market Intelligence B2B strict.

━━━ DÉFINITIONS OPÉRATIONNELLES ━━━

SI (Systèmes d'Information) — ce qui change les DÉCISIONS des DSI :
  • Annonces cloud enterprise : nouveaux services, contrats, migrations (AWS/Azure/GCP en contexte B2B)
  • Cybersécurité enterprise : incidents majeurs, nouvelles réglementations, outils de gouvernance
  • ERP/CRM/Data : annonces SAP, Oracle, Salesforce, Snowflake avec impact enterprise concret
  • Infrastructure : acquisitions, fusions, nouveaux acteurs qui reconfigurent le marché
  • Souveraineté numérique, conformité réglementaire (NIS2, DORA, AI Act)
  • Stratégie SI : outsourcing, insourcing, modernisation du legacy

GL (Génie Logiciel) — ce qui change les PRATIQUES des équipes engineering enterprise :
  • DevOps/Platform Engineering : nouvelles pratiques, retours d'expérience à l'échelle
  • CI/CD et outillage : releases majeures ou évolutions significatives d'outils enterprise
  • Qualité logicielle : testing industriel, dette technique, SRE, observabilité
  • Sécurité applicative : SAST/DAST, supply chain logicielle, SBOM, nouvelles obligations légales
  • Industrialisation IA : intégration IA dans pipelines de dev, impact sur les équipes engineering
  • Cas enterprise concrets : retours d'expérience de grandes entreprises sur leurs pratiques GL
  • Standards et tendances : releases langage/framework majeurs, rapports de conférences (QCon, KubeCon...)

━━━ REJETS STRICTS ━━━

REJETTE IMMÉDIATEMENT :
  • Gadgets, smartphones, montres, consoles, audio grand public
  • Guides pas-à-pas sur des blogs vendor ("comment faire X avec notre outil en 5 étapes")
  • Articles en plusieurs parties de type tutoriel ("Part 1", "Part 2"...)
  • Articles anniversaire/rétrospectif sans annonce ni enseignement concret
  • People news, nominations sans impact stratégique SI/GL démontrable
  • IA généraliste grand public (features ChatGPT consumer, Gemini grand public)
  • Résultats financiers purs sans lien avec la stratégie IT enterprise
  • Communiqués de presse vendor purs sans cas client ni chiffre concret

ATTENTION — NE PAS REJETER :
  • Retours d'expérience enterprise (même sur un blog vendor si le cas client est réel et nommé)
  • Releases majeures de langages/outils enterprise (Java, Kubernetes, GitLab...)
  • Études ou recherches sur l'impact des pratiques GL en entreprise
  • Articles de conférence (QCon, KubeCon, DevOps Days) avec enseignements concrets
  • Évolutions réglementaires touchant les pratiques GL (SBOM légal, NIS2 applicatif...)

━━━ SCORING ━━━

Pour SI :
80-100 : Annonce concrète + impact enterprise démontrable + acteur majeur
         (acquisition confirmée, contrat signé, réglementation adoptée, incident majeur analysé)
60-79  : News pertinente B2B sans chiffres/contrat, ou impact indirect mais clair
40-59  : Tendance intéressante mais trop générique ou trop early-stage
REJECT : Critères de rejet stricts

Pour GL :
75-100 : Retour d'expérience enterprise concret, ou évolution réglementaire GL, ou release
         majeure d'outil enterprise avec impact démontré sur les pratiques
60-74  : News GL pertinente avec cas réel ou chiffres, impact sur équipes engineering
45-59  : Tendance ou release intéressante mais sans preuve d'adoption enterprise
REJECT : Tuto pas-à-pas, blog vendor sans cas client, contenu purement B2C

━━━ RÈGLE D'OR ━━━
Pour SI : "Un DSI de Renault/BNP/Orange va-t-il changer une décision après cet article ?"
Pour GL : "Un tech lead ou CTO va-t-il changer une pratique d'équipe après cet article ?"
→ Non clairement : REJECT
→ Peut-être : score 45-59
→ Oui clairement : score 60+

PIÈGES FRÉQUENTS À ÉVITER :
  • "Comment faire X en 5 étapes avec notre outil" → REJECT (tuto vendor)
  • "Amazon S3 fête ses 20 ans" → score max 45 (rétrospective)
  • Release Java 26 / Kubernetes majeur → GL 65+ (impact enterprise réel)
  • Retour d'expérience Uber/Capital One/Netflix sur leurs pratiques → GL 70+
  • QCon/KubeCon : résumé de conférence avec enseignements → GL 60+
  • Rapport ANSSI/Gartner → SI 75+ (impact enterprise réel)
  • SBOM devient obligation légale → GL 80+ (changement réglementaire)

Réponds UNIQUEMENT en JSON valide, sans markdown, sans commentaires."""


def build_user_prompt(article: Article) -> str:
    content_preview = (article.content or article.summary)[:1500]
    return f"""Analyse cet article pour un Market Intelligence B2B enterprise.

SOURCE : {article.source}
TITRE : {article.title}
CONTENU : {content_preview}

INSTRUCTIONS :
1. Vérifie d'abord les critères de rejet strict (tuto vendor, B2C, anniversaire sans annonce, people news)
2. Si rejet : category=REJECT, score=0, explique POURQUOI c'est rejeté dans justification
3. Sinon : détermine SI ou GL selon les définitions opérationnelles
4. Score honnête : un blog vendor sans annonce concrète ne dépasse pas 50

Réponds avec exactement ce JSON (aucun autre texte) :
{{
  "category": "SI ou GL ou REJECT",
  "score": <entier 0-100>,
  "justification": "<2-3 phrases précises : pourquoi cette catégorie, pourquoi ce score, quel impact concret pour un DSI enterprise>",
  "is_b2c": <true ou false>,
  "summary": "<1 phrase factuelle résumant l'annonce principale pour un DSI, en français>"
}}"""


class ClaudeClient:
    def __init__(self, api_key: str = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Clé API Anthropic manquante. "
                "Définissez ANTHROPIC_API_KEY dans votre environnement."
            )
        self.model = model
        self.client = httpx.Client(timeout=30)
        self._call_count = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def classify(self, article: Article, retry: int = 2) -> ClassificationResult:
        prompt = build_user_prompt(article)

        for attempt in range(retry + 1):
            try:
                response = self.client.post(
                    ANTHROPIC_API_URL,
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 400,
                        "system": SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )

                if response.status_code == 429:
                    wait = 2 ** attempt * 5
                    print(f"    ⏳ Rate limit, attente {wait}s...")
                    time.sleep(wait)
                    continue

                if response.status_code != 200:
                    err = response.text[:300]
                    print(f"    ❌ API HTTP {response.status_code}: {err}")
                    return ClassificationResult(
                        category="REJECT", score=0,
                        justification=f"Erreur API HTTP {response.status_code}",
                        is_b2c=False, summary="", error=err,
                    )

                data = response.json()

                if "content" not in data or not data["content"]:
                    print(f"    ❌ Réponse API vide : {data}")
                    return ClassificationResult(
                        category="REJECT", score=0,
                        justification="Réponse API vide",
                        is_b2c=False, summary="", error=str(data),
                    )

                usage = data.get("usage", {})
                self._call_count += 1
                self._total_input_tokens += usage.get("input_tokens", 0)
                self._total_output_tokens += usage.get("output_tokens", 0)

                raw_text = data["content"][0]["text"].strip()
                # Nettoie les backticks markdown potentiels
                if raw_text.startswith("```"):
                    raw_text = raw_text.split("```")[1]
                    if raw_text.startswith("json"):
                        raw_text = raw_text[4:]
                    raw_text = raw_text.strip()

                parsed = json.loads(raw_text)
                return ClassificationResult(
                    category=parsed.get("category", "REJECT").upper(),
                    score=int(parsed.get("score", 0)),
                    justification=parsed.get("justification", ""),
                    is_b2c=bool(parsed.get("is_b2c", False)),
                    summary=parsed.get("summary", ""),
                    raw_response=raw_text,
                )

            except json.JSONDecodeError as e:
                print(f"    ⚠️  JSON invalide (tentative {attempt+1}) : {e}")
                if attempt < retry:
                    time.sleep(1)
                    continue
                return ClassificationResult(
                    category="REJECT", score=0,
                    justification="Erreur parsing JSON réponse LLM",
                    is_b2c=False, summary="", error=str(e),
                )
            except Exception as e:
                print(f"    ⚠️  Erreur inattendue (tentative {attempt+1}) : {e}")
                if attempt < retry:
                    time.sleep(2)
                    continue
                return ClassificationResult(
                    category="REJECT", score=0,
                    justification="Erreur appel API",
                    is_b2c=False, summary="", error=str(e),
                )

        return ClassificationResult(
            category="REJECT", score=0,
            justification="Échec après retry",
            is_b2c=False, summary="", error="max_retry_exceeded",
        )

    def classify_batch(
        self,
        articles: list,
        delay: float = 0.3,
        verbose: bool = True,
    ) -> list:
        results = []
        total = len(articles)

        for i, art in enumerate(articles, 1):
            if verbose:
                print(f"  🤖 [{i}/{total}] {art.title[:70]}...")

            result = self.classify(art)

            if verbose:
                icon = {"SI": "🔵", "GL": "🟢", "REJECT": "❌"}.get(result.category, "❓")
                status = f"{icon} {result.category} | score: {result.score}/100"
                if result.error:
                    status += f" | ⚠️  {result.error[:80]}"
                print(f"       {status}")

            results.append((art, result))

            if i < total:
                time.sleep(delay)

        return results

    def cost_estimate(self) -> dict:
        # Tarifs Haiku 4.5 : $0.80/1M input, $4.00/1M output
        input_cost = (self._total_input_tokens / 1_000_000) * 0.80
        output_cost = (self._total_output_tokens / 1_000_000) * 4.00
        return {
            "calls": self._call_count,
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
            "estimated_cost_usd": round(input_cost + output_cost, 4),
        }


def fallback_classify(article: Article, si_keywords: list, gl_keywords: list) -> ClassificationResult:
    from processor import keyword_score, is_b2c

    if is_b2c(article):
        return ClassificationResult(
            category="REJECT", score=0,
            justification="Rejeté : contenu B2C détecté (règles locales).",
            is_b2c=True, summary=article.summary[:200],
        )

    si_score = keyword_score(article, si_keywords)
    gl_score = keyword_score(article, gl_keywords)

    if si_score == 0 and gl_score == 0:
        return ClassificationResult(
            category="REJECT", score=0,
            justification="Aucun mot-clé SI/GL détecté.",
            is_b2c=False, summary=article.summary[:200],
        )

    if si_score >= gl_score:
        cat, raw = "SI", min(si_score * 10, 90)
    else:
        cat, raw = "GL", min(gl_score * 10, 90)

    return ClassificationResult(
        category=cat, score=raw,
        justification=f"Classification par règles locales : {si_score} mots-clés SI, {gl_score} mots-clés GL.",
        is_b2c=False, summary=article.summary[:200],
    )
