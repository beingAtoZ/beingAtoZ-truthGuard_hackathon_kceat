"""
Fact Checker Service
Cross-references extracted claims against:
  1. Google Fact Check Tools API (primary)
  2. Heuristic keyword fallback (if no API key or API fails)

Improvements:
  - Strips placeholder API key value so it isn't accidentally sent
  - Expanded heuristic keyword lists for better fallback coverage
  - Added credibility source label for heuristic results
"""
import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()
_raw_key = os.getenv("GOOGLE_FACT_CHECK_API_KEY", "").strip()
# Strip placeholder so it isn't accidentally used
FACT_CHECK_API_KEY = "" if _raw_key in ("your_google_fact_check_api_key_here", "") else _raw_key
FACT_CHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

VERDICT_NORMALIZE = {
    # True-ish
    "true":          ("confirmed", "Confirmed True"),
    "correct":       ("confirmed", "Confirmed True"),
    "accurate":      ("confirmed", "Confirmed True"),
    "mostly true":   ("confirmed", "Mostly True"),
    "verified":      ("confirmed", "Verified"),
    # False-ish
    "false":         ("false", "Confirmed False"),
    "incorrect":     ("false", "Confirmed False"),
    "mostly false":  ("false", "Mostly False"),
    "pants on fire": ("false", "Pants on Fire"),
    "wrong":         ("false", "Confirmed False"),
    "untrue":        ("false", "Confirmed False"),
    "inaccurate":    ("false", "Inaccurate"),
    # Mixed
    "mixed":           ("mixed", "Mixed / Partially True"),
    "half true":       ("mixed", "Half True"),
    "partly false":    ("mixed", "Partly False"),
    "misleading":      ("mixed", "Misleading"),
    "missing context": ("mixed", "Missing Context"),
    "partially":       ("mixed", "Partially Accurate"),
    "unproven":        ("unverified", "Unproven"),
    "unverified":      ("unverified", "Unverified"),
}

async def cross_check_claims(claims: list[str]) -> list[dict]:
    """
    Takes up to 3 claims and returns fact-check results.
    Each result: {claim, verdict, label, source}
    """
    if not claims:
        return _default_evidence()

    tasks = [_check_single_claim(c) for c in claims[:3]]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    evidence = []
    for i, r in enumerate(results):
        if isinstance(r, Exception) or r is None:
            evidence.append({
                "claim": claims[i][:150],
                "verdict": "unverified",
                "label": "Unverified",
                "source": "Could not retrieve fact-check data"
            })
        else:
            evidence.append(r)

    return evidence if evidence else _default_evidence()


async def _check_single_claim(claim: str) -> dict | None:
    """Query Google Fact Check API for a single claim."""
    short_claim = claim[:200]

    if FACT_CHECK_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(FACT_CHECK_URL, params={
                    "key": FACT_CHECK_API_KEY,
                    "query": short_claim,
                    "languageCode": "en",
                    "pageSize": 1
                })
                data = resp.json()
                items = data.get("claims", [])
                if items:
                    item = items[0]
                    rating_text = ""
                    source_name = ""
                    review = item.get("claimReview", [])
                    if review:
                        rating_text = review[0].get("textualRating", "").lower()
                        source_name = review[0].get("publisher", {}).get("name", "")

                    verdict, label = _normalize_verdict(rating_text)
                    return {
                        "claim": item.get("text", short_claim)[:150],
                        "verdict": verdict,
                        "label": label,
                        "source": source_name or "Google Fact Check"
                    }
        except Exception:
            pass  # Fall through to heuristic

    # ── Heuristic fallback ──
    return _heuristic_fact_check(short_claim)


def _normalize_verdict(rating: str) -> tuple[str, str]:
    """Map raw rating text to standardized verdict."""
    rating = rating.lower().strip()
    for key, val in VERDICT_NORMALIZE.items():
        if key in rating:
            return val
    return ("unverified", "Unverified")


def _heuristic_fact_check(claim: str) -> dict:
    """
    Keyword-based fallback fact-check.
    Expanded lists for better coverage of real news patterns.
    """
    claim_lower = claim.lower()

    # Strong false indicators
    false_keywords = [
        "government hiding", "secret cure", "they won't tell", "microchip",
        "hoax", "crisis actor", "deep state", "plandemic", "miracle cure",
        "big pharma hiding", "what doctors won't", "censored by",
        "shadow government", "chemtrails", "5g causes", "vaccine chip",
    ]
    # Strong true indicators
    true_keywords = [
        "scientists confirm", "study shows", "data published", "officials announced",
        "according to", "research finds", "peer-reviewed", "published in",
        "confirmed by", "in a statement", "told reporters", "official data",
        "clinical trial", "health authorities confirm", "government announced",
        "survey found", "statistics show",
    ]
    # Mixed/uncertain indicators
    mixed_keywords = [
        "some experts", "disputed", "debated", "controversial", "claims that",
        "alleged", "unconfirmed reports", "sources say", "reportedly",
        "it is believed", "many claim", "circulating online",
    ]

    if any(k in claim_lower for k in false_keywords):
        return {"claim": claim[:150], "verdict": "false",      "label": "Likely False",     "source": "Heuristic Analysis"}
    elif any(k in claim_lower for k in true_keywords):
        return {"claim": claim[:150], "verdict": "confirmed",  "label": "Likely True",      "source": "Heuristic Analysis"}
    elif any(k in claim_lower for k in mixed_keywords):
        return {"claim": claim[:150], "verdict": "mixed",      "label": "Mixed / Disputed", "source": "Heuristic Analysis"}
    else:
        return {"claim": claim[:150], "verdict": "unverified", "label": "Unverified",       "source": "No matching records"}


def _default_evidence() -> list[dict]:
    return [{
        "claim": "No specific verifiable claims were extracted",
        "verdict": "unverified",
        "label": "Unverified",
        "source": "Insufficient claim data"
    }]
