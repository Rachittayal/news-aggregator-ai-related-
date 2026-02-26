import os
import re
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

from groq import Groq
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


# ---------- Output schema your pipeline expects ----------
class RankedArticle(BaseModel):
    digest_id: str = Field(description="The ID of the digest (article_type:article_id)")
    relevance_score: float = Field(description="Relevance score from 0.0 to 10.0", ge=0.0, le=10.0)
    rank: int = Field(description="Rank position (1 = most relevant)", ge=1)
    reasoning: str = Field(description="Brief explanation of why this article is ranked here")


class RankedDigestList(BaseModel):
    articles: List[RankedArticle] = Field(description="List of ranked articles")


# ---------- Prompt (LLM should return SMALL JSON only) ----------
LLM_SCORE_PROMPT = """You are an AI news curator.

You will receive a list of digests (id, title, summary, type) and a user profile.
Your job: assign a relevance_score (0.0 to 10.0) for EACH digest.

IMPORTANT OUTPUT RULES:
- Return ONLY valid JSON
- Do NOT include markdown
- Do NOT include explanations outside JSON
- Do NOT include rank
- JSON format must be EXACTLY:
{
  "articles": [
    {"digest_id": "...", "relevance_score": 7.5},
    ...
  ]
}
"""


# ---------- Helper utils ----------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _tokenize(text: str) -> List[str]:
    # simple, fast tokenizer
    text = (text or "").lower()
    tokens = re.findall(r"[a-z0-9]{4,}", text)
    return tokens


def _extract_json(text: str) -> str:
    text = (text or "").strip()

    # remove code fences if model used them
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].strip()
            text = re.sub(r"^\s*json\s*", "", text, flags=re.IGNORECASE).strip()

    # extract outermost JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")

    return text[start : end + 1]


# ---------- The professional CuratorAgent ----------
class CuratorAgent:
    """
    Professional hybrid ranker:
      A) Deterministic pre-rank (cheap, stable)
      B) LLM scoring on small shortlist (Groq free-tier safe)
      C) Fallback to heuristic ranking if LLM fails
    """

    def __init__(self, user_profile: dict):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.1-8b-instant"
        self.user_profile = user_profile

        # Build interest vocabulary once
        interests_text = " ".join(user_profile.get("interests", []))
        self.interest_tokens = set(_tokenize(interests_text))

        # Optional preference boost words (tune anytime)
        prefs = user_profile.get("preferences", {}) or {}
        self.boost_terms = set()
        if prefs.get("prefer_system_design"):
            self.boost_terms.update(["architecture", "pipeline", "scalability", "latency", "reliability"])
        if prefs.get("prefer_implementation_details"):
            self.boost_terms.update(["implementation", "benchmark", "evaluation", "metrics", "code"])
        if prefs.get("prefer_production_realism"):
            self.boost_terms.update(["production", "deployment", "monitoring", "incident", "cost"])

        self.down_terms = set()
        if prefs.get("avoid_marketing_hype"):
            self.down_terms.update(["webinar", "register", "limited", "launch", "partnership"])

    # ---------- Stage A: deterministic pre-rank ----------
    def _heuristic_score(self, d: Dict[str, Any]) -> Tuple[float, str]:
        title = d.get("title", "") or ""
        summary = d.get("summary", "") or ""
        t = f"{title} {summary}"

        toks = set(_tokenize(t))
        interest_hits = len(toks & self.interest_tokens)
        boost_hits = len(toks & self.boost_terms)
        down_hits = len(toks & self.down_terms)

        base = interest_hits * 1.2 + boost_hits * 0.8 - down_hits * 0.7

        # recency boost if created_at exists
        recency = 0.0
        created_at = d.get("created_at")
        try:
            if isinstance(created_at, datetime):
                age_h = max(0.0, (_now_utc() - created_at.astimezone(timezone.utc)).total_seconds() / 3600.0)
                recency = max(0.0, 1.5 - (age_h / 24.0) * 1.5)
        except Exception:
            pass

        score = base + recency
        why = f"interest={interest_hits}, boost={boost_hits}, recency={recency:.2f}"
        return score, why

    def _pre_rank(self, digests: List[dict], keep: int) -> List[dict]:
        scored = []
        for d in digests:
            s, why = self._heuristic_score(d)
            d2 = dict(d)
            d2["_heur_score"] = s
            d2["_heur_why"] = why
            scored.append(d2)

        scored.sort(key=lambda x: x["_heur_score"], reverse=True)
        return scored[:keep]

    # ---------- Stage B: LLM scoring (small output) ----------
    def _llm_score(self, shortlisted: List[dict]) -> Dict[str, float]:
        # Keep prompt small: id/title/summary/type only
        digest_list = "\n\n".join([
            f"ID: {d['id']}\nTitle: {d['title']}\nSummary: {d['summary']}\nType: {d['article_type']}"
            for d in shortlisted
        ])

        profile = self.user_profile
        system = f"""{LLM_SCORE_PROMPT}

User Profile:
Name: {profile.get("name")}
Background: {profile.get("background")}
Expertise Level: {profile.get("expertise_level")}
Interests: {", ".join(profile.get("interests", []))}"""

        user_prompt = f"""Score these {len(shortlisted)} digests by relevance. Return JSON only.

{digest_list}
"""

        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            max_tokens=450,  # small JSON output only
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = (resp.choices[0].message.content or "").strip()
        json_text = _extract_json(text)
        data = json.loads(json_text)

        scores = {}
        for item in data.get("articles", []):
            did = item.get("digest_id")
            sc = item.get("relevance_score")
            if did and isinstance(sc, (int, float)):
                scores[did] = float(sc)
        return scores

    # ---------- Public method used by your pipeline ----------
    def rank_digests(self, digests: List[dict]) -> List[RankedArticle]:
        if not digests:
            return []

        # 1) Pre-rank in Python (stable)
        PRE_RANK_KEEP = 25  # safe for free tier
        shortlisted = self._pre_rank(digests, keep=min(PRE_RANK_KEEP, len(digests)))

        # 2) LLM scores only shortlisted items
        try:
            llm_scores = self._llm_score(shortlisted)

            # merge: if LLM missed any id, fallback to heuristic score mapping
            # normalize heuristic to 0..10 approx
            final_rows = []
            for d in shortlisted:
                did = d["id"]
                if did in llm_scores:
                    score = max(0.0, min(10.0, llm_scores[did]))
                    reasoning = "LLM relevance score (shortlisted after heuristic pre-rank)"
                else:
                    # fallback for missing id
                    score = max(0.0, min(10.0, 3.0 + min(7.0, d["_heur_score"])))
                    reasoning = f"Fallback heuristic (LLM did not return score): {d['_heur_why']}"

                final_rows.append((did, score, reasoning))

        except Exception as e:
            # 3) Fallback: purely heuristic ranking (pipeline never breaks)
            print(f"LLM ranking failed, falling back to heuristic ranking: {e}")
            final_rows = []
            for d in shortlisted:
                score = max(0.0, min(10.0, 3.0 + min(7.0, d["_heur_score"])))
                final_rows.append((d["id"], score, f"Heuristic ranking (no LLM): {d['_heur_why']}"))

        # 4) Sort and assign rank in Python (deterministic)
        final_rows.sort(key=lambda x: x[1], reverse=True)

        ranked: List[RankedArticle] = []
        for idx, (digest_id, score, reasoning) in enumerate(final_rows, start=1):
            ranked.append(RankedArticle(
                digest_id=digest_id,
                relevance_score=score,
                rank=idx,
                reasoning=reasoning
            ))

        return ranked