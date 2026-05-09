"""
LLM Explanation Service
Generates a dynamic human-readable explanation of the verdict based on extracted signals.
"""

def generate_explanation(
    text: str,
    verdict: str,
    confidence: float,
    claims: list[str],
    sentiment: str
) -> str:
    """
    Generate a concise, plain-English explanation for the verdict based on signals.
    """
    claims_text = (
        f"with {len(claims)} verifiable claims extracted"
        if claims else "with no verifiable claims extracted"
    )

    if verdict == "REAL":
        return (
            f"This content appears credible with {confidence:.0f}% confidence. "
            f"The writing style is factual with a {sentiment} tone, {claims_text}. "
            "Source credibility signals and language patterns are consistent with "
            "legitimate, verifiable reporting from established outlets."
        )
    elif verdict == "FAKE":
        return (
            f"This content was classified as FAKE with {confidence:.0f}% confidence. "
            f"The analysis detected {sentiment} sentiment patterns {claims_text}, "
            "none of which could be corroborated by trusted sources. "
            "Multiple misinformation signals including sensationalist language, "
            "unverifiable assertions, and absence of credible citations were identified."
        )
    elif verdict == "MISLEADING":
        return (
            f"This content was flagged as MISLEADING ({confidence:.0f}% confidence). "
            f"While it contains a {sentiment} tone {claims_text}, the structural analysis "
            "detected significant bias, out-of-context framing, or highly sensationalized "
            "language typical of clickbait or partisan aggregation."
        )
    else:
        return (
            f"This content remains UNVERIFIED (confidence: {confidence:.0f}%). "
            f"It exhibits a {sentiment} tone {claims_text}. The internal pipeline "
            "could not conclusively categorize the text as factual or fabricated due to "
            "insufficient structural evidence or mixed credibility signals."
        )
