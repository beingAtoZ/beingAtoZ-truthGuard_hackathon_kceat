"""
Source Credibility Service
Scores a domain 0–100 based on:
  - Known credible/fake domain lists
  - Domain age via python-whois
  - URL structure heuristics
  - Content signals from NLP data (when no URL is provided)

BUG FIX: For manual text input (no URL/domain), the original code always
returned a hardcoded score of 50, preventing the pipeline's credibility-based
verdict adjustments from ever firing on text input. Now derives a pseudo-
credibility score from NLP content signals (clickbait, emotion, claim count,
structural quality) so text-only analysis gets meaningful credibility context.
"""
import re
from urllib.parse import urlparse

# ── Curated domain lists ──
CREDIBLE_DOMAINS = {
    "reuters.com": 95, "apnews.com": 95, "bbc.com": 92, "bbc.co.uk": 92,
    "theguardian.com": 88, "nytimes.com": 87, "washingtonpost.com": 86,
    "economist.com": 90, "nature.com": 95, "science.org": 95,
    "who.int": 97, "cdc.gov": 96, "nih.gov": 96, "gov.uk": 94,
    "npr.org": 88, "pbs.org": 87, "time.com": 82, "forbes.com": 78,
    "bloomberg.com": 85, "ft.com": 88, "wsj.com": 84,
    "snopes.com": 85, "factcheck.org": 88, "politifact.com": 87,
    "fullfact.org": 88, "afpfactcheck.org": 87,
    "aljazeera.com": 80, "dw.com": 85, "france24.com": 82,
    "thehindu.com": 78, "ndtv.com": 72, "indiatoday.in": 70,
}

FAKE_DOMAINS = {
    "beforeitsnews.com": 5, "naturalnews.com": 8, "infowars.com": 4,
    "worldnewsdailyreport.com": 3, "theonion.com": 15,  # satire
    "clickhole.com": 15, "empirenews.net": 4, "nationalreport.net": 4,
    "abcnews.com.co": 3, "cbsnews.com.co": 3, "conservativedailypost.com": 10,
    "yournewswire.com": 5, "newspunch.com": 5, "zerohedge.com": 22,
    "thegatewaypundit.com": 12, "100percentfedup.com": 8,
}

SUSPICIOUS_PATTERNS = [
    r"\.com\.co$", r"\.(news|media)\.(co|info|net)$",
    r"breaking[_-]?news", r"real[_-]?truth", r"truth[_-]?news",
    r"\d{4}news", r"daily[_-]?buzz", r"patriot[_-]?(news|daily|report)",
]


def score_source_credibility(
    url: str | None,
    domain: str = "",
    nlp_data: dict | None = None
) -> dict:
    """Returns credibility score and details for a given URL/domain."""

    if not url and not domain:
        return _score_from_content_signals(nlp_data)

    # Extract domain
    if not domain and url:
        try:
            parsed = urlparse(url if url.startswith("http") else "http://" + url)
            domain = parsed.netloc.lower().replace("www.", "")
        except Exception:
            domain = url

    details = []
    score = 50  # neutral start

    # ── Check known lists ──
    if domain in CREDIBLE_DOMAINS:
        score = CREDIBLE_DOMAINS[domain]
        details.append(f"✅ {domain} is in verified credible sources list")
    elif domain in FAKE_DOMAINS:
        score = FAKE_DOMAINS[domain]
        details.append(f"❌ {domain} is flagged as known misinformation source")
    else:
        details.append(f"ℹ️ {domain} not in known credible/fake database")

    # ── Suspicious pattern check ──
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, domain):
            score = max(5, score - 25)
            details.append("⚠️ Domain name matches suspicious URL pattern")
            break

    # ── TLD scoring ──
    if domain.endswith(".gov") or domain.endswith(".edu"):
        score = min(97, score + 15)
        details.append("✅ Government/educational domain (.gov/.edu)")
    elif domain.endswith(".org"):
        score = min(90, score + 5)
        details.append("ℹ️ Non-profit domain (.org) — moderate trust signal")
    elif domain.endswith((".info", ".biz", ".xyz", ".click")):
        score = max(10, score - 20)
        details.append("⚠️ Low-trust TLD (.info/.biz/.xyz)")

    # ── Domain age via whois ──
    try:
        import whois
        import datetime
        w = whois.query(domain)
        if w and w.creation_date:
            age_years = (datetime.datetime.now() - w.creation_date).days / 365
            if age_years >= 10:
                score = min(100, score + 10)
                details.append(f"✅ Domain is {age_years:.0f}+ years old — established")
            elif age_years >= 3:
                details.append(f"ℹ️ Domain age: {age_years:.1f} years")
            else:
                score = max(5, score - 15)
                details.append(f"⚠️ Domain is only {age_years:.1f} years old — new")
    except Exception:
        details.append("ℹ️ Domain age could not be verified")

    # ── HTTPS check ──
    if url and url.startswith("https://"):
        details.append("✅ HTTPS enabled")
    elif url:
        score = max(5, score - 5)
        details.append("⚠️ No HTTPS — insecure connection")

    score = max(0, min(100, round(score)))
    return {"score": score, "domain": domain, "details": details[:5]}


def _score_from_content_signals(nlp_data: dict | None) -> dict:
    """
    Derive pseudo-credibility score from NLP content signals when no URL
    is available. Starts at a neutral 55 and adjusts based on writing quality.

    BUG FIX: Previously always returned 50 (hardcoded), which meant the
    pipeline's credibility guard never fired for manual text input.
    """
    score = 55  # Slightly above neutral — benefit of the doubt for direct input
    details = ["ℹ️ No URL provided — credibility estimated from content signals"]

    if not nlp_data:
        details.append("ℹ️ No content signals available")
        return {"score": score, "domain": "Direct text input", "details": details}

    # Clickbait language → lower trust
    if nlp_data.get("is_clickbait"):
        score -= 15
        details.append("⚠️ Clickbait-style language detected in content")

    # Heavy emotional language → lower trust
    if nlp_data.get("high_emotion"):
        score -= 10
        details.append("⚠️ High emotional / sensationalist language")

    # No extractable claims → less verifiable
    claim_count = len(nlp_data.get("claims", []))
    if claim_count == 0:
        score -= 8
        details.append("⚠️ No verifiable claims could be extracted")
    elif claim_count >= 2:
        score += 5
        details.append(f"✅ {claim_count} verifiable claims extracted from text")

    # Named entities → sign of specific, factual reporting
    entity_count = len(nlp_data.get("entities", []))
    if entity_count >= 5:
        score += 8
        details.append(f"✅ {entity_count} named entities found — specific reporting")
    elif entity_count == 0:
        score -= 5
        details.append("⚠️ No named entities found — vague content")

    # Very short text → insufficient for confident assessment
    word_count = nlp_data.get("word_count", 0)
    if word_count < 30:
        score -= 10
        details.append("⚠️ Very short text — insufficient for reliable analysis")
    elif word_count >= 150:
        score += 5
        details.append("✅ Sufficient text length for analysis")

    # Negative-heavy sentiment combined with sensationalism
    if nlp_data.get("sentiment") == "negative" and nlp_data.get("high_emotion"):
        score -= 5
        details.append("⚠️ Negative + high-emotion combination — bias signal")

    score = max(10, min(90, round(score)))  # Cap: never fully trust/distrust text-only
    return {
        "score": score,
        "domain": "Direct text input",
        "details": details[:5]
    }
