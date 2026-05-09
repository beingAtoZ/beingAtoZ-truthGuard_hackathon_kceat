"""
Main AI Pipeline — orchestrates NLP → classification → credibility → fact-check → LLM

Fixes applied:
  - nlp_data is now passed to score_source_credibility so text-only input
    gets a meaningful content-derived credibility score (not hardcoded 50)
  - Added "contradicts" signal handling in verdict adjustment
  - Confidence is now clamped to a sensible range before output
  - Added api_used field propagated from news_search to response
  - Structural signals (avg sentence length, word count) feed into tags
"""
import asyncio
from services.nlp_service import preprocess_and_extract
from services.classifier import classify_text
from services.credibility import score_source_credibility
from services.fact_checker import cross_check_claims
from services.llm_service import generate_explanation
from services.news_search import search_verified_news

VERDICT_MAP = {
    "fake":        "FAKE",
    "real":        "REAL",
    "misleading":  "MISLEADING",
    "unverified":  "UNVERIFIED",
}

COLOR_MAP = {
    "FAKE":       "fake",
    "REAL":       "real",
    "MISLEADING": "misleading",
    "UNVERIFIED": "unverified",
}


async def run_pipeline(
    text: str,
    source_url: str | None,
    input_type: str,
    title: str = "",
    domain: str = ""
) -> dict:
    """Full analysis pipeline. Returns structured result dict."""

    # Step 1 — NLP preprocessing (sync, fast)
    nlp_data = preprocess_and_extract(text)

    # Step 2 — Classification + Credibility + Fact-check + News Search in parallel
    # BUG FIX: Pass nlp_data to credibility so text-only input isn't stuck at 50
    classification_task = asyncio.to_thread(classify_text, text)
    credibility_task    = asyncio.to_thread(
        score_source_credibility, source_url, domain, nlp_data
    )
    fact_task  = cross_check_claims(nlp_data["claims"])
    news_task  = search_verified_news(text[:300], nlp_data["claims"], nlp_data.get("entities", []))

    classification, credibility, fact_results, verified_news = await asyncio.gather(
        classification_task, credibility_task, fact_task, news_task
    )

    # Step 3 — Determine final verdict
    raw_verdict = classification["label"].upper()
    verdict     = VERDICT_MAP.get(raw_verdict, raw_verdict)
    confidence  = round(classification["score"] * 100, 1)

    # ── Credibility guard ──
    # Very low credibility source → downgrade from REAL to MISLEADING
    if credibility["score"] < 25 and verdict == "REAL":
        verdict    = "MISLEADING"
        confidence = min(confidence, 62.0)

    # Moderate-low credibility + borderline confidence → flag as unverified
    elif credibility["score"] < 45 and verdict == "REAL" and confidence < 70:
        verdict    = "UNVERIFIED"
        confidence = min(confidence, 65.0)

    # ── News signal adjustment ──
    news_signal = verified_news.get("verdict_signal", "not_found")

    if news_signal == "corroborates" and verdict == "REAL":
        # Trusted outlets cover the same story → small confidence boost
        confidence = min(99.0, confidence + 5.0)

    elif news_signal == "contradicts":
        # Trusted outlets debunk the story → downgrade verdict
        if verdict in ("REAL", "UNVERIFIED"):
            verdict    = "MISLEADING"
            confidence = min(confidence, 60.0)
        elif verdict == "FAKE":
            # Debunking corroborates our FAKE verdict → boost confidence
            confidence = min(99.0, confidence + 8.0)

    elif news_signal == "not_found" and verdict == "REAL" and confidence < 70:
        # Can't find corroborating coverage → flag as unverified
        verdict    = "UNVERIFIED"
        confidence = min(confidence, 62.0)

    # ── Fact-check evidence override ──
    confirmed_count = sum(1 for e in fact_results if e.get("verdict") == "confirmed")
    false_count     = sum(1 for e in fact_results if e.get("verdict") == "false")

    if false_count > 0 and verdict == "REAL":
        verdict    = "MISLEADING"
        confidence = min(confidence, 65.0)
    elif confirmed_count >= 2 and verdict in ("UNVERIFIED", "MISLEADING"):
        verdict    = "REAL"
        confidence = max(confidence, 65.0)

    # Final confidence clamp
    confidence = max(10.0, min(99.0, confidence))

    # Step 4 — LLM explanation (async)
    explanation = generate_explanation(
        text=text[:1500],
        verdict=verdict,
        confidence=confidence,
        claims=nlp_data["claims"],
        sentiment=nlp_data["sentiment"]
    )

    # Step 5 — Build response tags
    tags = [
        f"Sentiment: {nlp_data['sentiment'].title()}",
        f"Entities: {len(nlp_data['entities'])} found",
        f"Claims extracted: {len(nlp_data['claims'])}",
        f"Input: {input_type.title()}",
        f"Words: {nlp_data.get('word_count', 0)}",
    ]
    if nlp_data.get("is_clickbait"):
        tags.append("⚠️ Clickbait headline detected")
    if nlp_data.get("high_emotion"):
        tags.append("⚠️ High emotional language")
    if verified_news.get("api_used") and verified_news["api_used"] not in ("none", "demo"):
        tags.append(f"🔎 Verified via {verified_news['api_used']}")
    elif verified_news.get("api_used") == "demo":
        tags.append("ℹ️ News search: illustrative data")
    else:
        tags.append("ℹ️ No live news API configured")

    return {
        "verdict":    verdict,
        "confidence": confidence,
        "color":      COLOR_MAP.get(verdict, "unverified"),
        "explanation": explanation,
        "source": {
            "domain":  domain or credibility.get("domain", "Direct input"),
            "score":   credibility["score"],
            "details": credibility["details"],
        },
        "evidence":      fact_results,
        "verified_news": verified_news,
        "tags":          tags,
        "nlp": {
            "entities":  nlp_data["entities"][:8],
            "claims":    nlp_data["claims"],
            "sentiment": nlp_data["sentiment"],
        }
    }
