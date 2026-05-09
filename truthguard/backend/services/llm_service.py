"""
LLM Explanation Service
Uses Google Gemini API to generate a human-readable explanation of the verdict.
Falls back to a template-based explanation if no API key is set.

Fix: Strips placeholder key value so template fallback is used cleanly
     instead of sending a dummy key to the Gemini API.
"""
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
_raw_key = os.getenv("GEMINI_API_KEY", "").strip()
# Strip placeholder values
GEMINI_API_KEY = "" if _raw_key in ("your_gemini_api_key_here", "") else _raw_key

_gemini_model = None

def _get_gemini():
    global _gemini_model
    if _gemini_model is None and GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            _gemini_model = genai.GenerativeModel("gemini-1.5-flash")
            print("[LLM] Gemini 1.5 Flash loaded")
        except Exception as e:
            print(f"[LLM] Gemini init failed: {e}")
            _gemini_model = False
    return _gemini_model


async def generate_explanation(
    text: str,
    verdict: str,
    confidence: float,
    claims: list[str],
    sentiment: str
) -> str:
    """
    Generate a concise, plain-English explanation for the verdict.
    Returns a 2–3 sentence string.
    """
    model = _get_gemini()

    if model:
        try:
            claims_str = "\n".join(f"- {c}" for c in claims[:3]) if claims else "- No specific claims extracted"
            prompt = f"""You are an expert AI fact-checker. Analyze this content and explain in 2-3 clear sentences why it is classified as '{verdict}' with {confidence:.0f}% confidence.

Content (excerpt): {text[:800]}

Key claims found:
{claims_str}

Sentiment detected: {sentiment}

Write a direct, factual explanation. Do not use bullet points. Be specific about what signals led to this verdict. Keep it under 80 words."""

            response = await asyncio.to_thread(
                model.generate_content, prompt
            )
            explanation = response.text.strip()
            if explanation:
                return explanation
        except Exception as e:
            print(f"[LLM] Generation error: {e}")

    # ── Template fallback ──
    return _template_explanation(verdict, confidence, sentiment, claims)


def _template_explanation(
    verdict: str,
    confidence: float,
    sentiment: str,
    claims: list
) -> str:
    claim_count = len(claims)
    claim_phrase = (
        f"with {claim_count} verifiable claim{'s' if claim_count != 1 else ''} extracted"
        if claim_count else "with no verifiable claims extracted"
    )

    templates = {
        "FAKE": (
            f"This content was classified as FAKE with {confidence:.0f}% confidence. "
            f"The analysis detected {sentiment} sentiment patterns {claim_phrase}, "
            "none of which could be corroborated by trusted sources. "
            "Multiple misinformation signals including sensationalist language, "
            "unverifiable assertions, and absence of credible citations were identified."
        ),
        "REAL": (
            f"This content appears credible with {confidence:.0f}% confidence. "
            f"The writing style is factual with a {sentiment} tone, {claim_phrase}. "
            "Source credibility signals and language patterns are consistent with "
            "legitimate, verifiable reporting from established outlets."
        ),
        "MISLEADING": (
            f"This content is classified as MISLEADING ({confidence:.0f}% confidence). "
            f"While it may contain factual elements, the {sentiment} framing omits "
            f"important context — {claim_phrase} show selective or partial use of facts. "
            "The overall narrative may distort reality without being entirely fabricated."
        ),
        "UNVERIFIED": (
            f"Insufficient evidence to make a high-confidence classification "
            f"({confidence:.0f}% certainty). "
            f"The content shows mixed signals: {sentiment} sentiment {claim_phrase}. "
            "No strong indicators of either confirmed credibility or known misinformation "
            "were detected. Independent verification from primary sources is recommended."
        ),
    }
    return templates.get(verdict, templates["UNVERIFIED"])
