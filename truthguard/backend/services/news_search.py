"""
News Search Service
Searches verified/trusted news channels online to cross-reference the story.
  Primary:   NewsAPI (newsapi.org)   — free tier: 100 req/day
  Secondary: GNews API (gnews.io)   — free tier: 100 req/day
  Fallback:  Returns honest "not_found" — no fabricated demo articles.

BUG FIX: The original _demo_search() returned hardcoded fake BBC/Reuters
articles regardless of input, causing verdict_signal="corroborates" for all
clean text. This silently boosted confidence in the pipeline for texts that
were never actually verified. Now, when no API keys are configured, we return
an honest not_found response. Enable DEMO_MODE=true in .env to restore
illustrative placeholders (clearly labelled).
"""
import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()
NEWS_API_KEY  = os.getenv("NEWS_API_KEY", "").strip()
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "").strip()
DEMO_MODE     = os.getenv("DEMO_MODE", "false").strip().lower() == "true"

# Strip placeholder values so they aren't accidentally used
if NEWS_API_KEY  in ("your_newsapi_key_here", ""):
    NEWS_API_KEY = ""
if GNEWS_API_KEY in ("your_gnews_api_key_here", ""):
    GNEWS_API_KEY = ""

NEWSAPI_URL = "https://newsapi.org/v2/everything"
GNEWS_URL   = "https://gnews.io/api/v4/search"

# Tier-1 verified sources
TRUSTED_SOURCES = {
    "bbc-news", "bbc.co.uk", "bbc.com",
    "reuters", "reuters.com",
    "associated-press", "apnews.com",
    "the-guardian-uk", "theguardian.com",
    "the-washington-post", "washingtonpost.com",
    "the-new-york-times", "nytimes.com",
    "al-jazeera-english", "aljazeera.com",
    "cnn", "cnn.com",
    "nbc-news", "nbcnews.com",
    "abc-news", "abcnews.go.com",
    "npr", "npr.org",
    "time", "time.com",
    "bloomberg", "bloomberg.com",
    "the-economist", "economist.com",
    "who.int", "cdc.gov", "nih.gov",
    "snopes.com", "factcheck.org", "politifact.com", "fullfact.org",
}

# Keywords that indicate an article is debunking a claim
DEBUNK_KEYWORDS = [
    "debunked", "fact check", "fact-check", "no evidence",
    "false claim", "misleading", "hoax", "clarifies", "refutes",
    "misinformation", "disinformation", "not true", "wrong",
]

async def search_verified_news(query: str, claims: list[str], entities: list[dict] = None) -> dict:
    """
    Search verified news channels for the given query/claims.
    Returns:
      {
        found: bool,
        match_count: int,
        articles: [ {title, source, url, published_at, is_trusted} ],
        verdict_signal: "corroborates" | "contradicts" | "not_found",
        api_used: str   ← new: transparency on data source
      }
    """
    search_query = _build_query(query, claims, entities)
    articles = []
    api_used = "none"

    if NEWS_API_KEY:
        articles = await _search_newsapi(search_query)
        if articles:
            api_used = "NewsAPI"

    if not articles and GNEWS_API_KEY:
        articles = await _search_gnews(search_query)
        if articles:
            api_used = "GNews"

    # Only use demo if explicitly enabled via env
    if not articles and DEMO_MODE:
        articles = _demo_search(search_query)
        api_used = "demo"

    found = len(articles) > 0
    verdict_signal = _infer_signal(articles, query)

    return {
        "found": found,
        "match_count": len(articles),
        "search_query": search_query,
        "articles": articles[:5],
        "verdict_signal": verdict_signal,
        "api_used": api_used,
    }


async def _search_newsapi(query: str) -> list[dict]:
    """Query NewsAPI /everything endpoint."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(NEWSAPI_URL, params={
                "q": query,
                "apiKey": NEWS_API_KEY,
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": 5,
            })
            data = resp.json()
            if data.get("status") != "ok":
                print(f"[NewsSearch] NewsAPI returned status: {data.get('status')} — {data.get('message','')}")
                return []
            return [
                {
                    "title": a.get("title", ""),
                    "source": a.get("source", {}).get("name", "Unknown"),
                    "url": a.get("url", ""),
                    "published_at": (a.get("publishedAt") or "")[:10],
                    "is_trusted": _is_trusted_source(
                        a.get("source", {}).get("id", ""), a.get("url", "")
                    ),
                }
                for a in data.get("articles", [])
                if a.get("title") and "[Removed]" not in a.get("title", "")
            ]
    except Exception as e:
        print(f"[NewsSearch] NewsAPI error: {e}")
        return []


async def _search_gnews(query: str) -> list[dict]:
    """Query GNews API as secondary fallback."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(GNEWS_URL, params={
                "q": query,
                "token": GNEWS_API_KEY,
                "lang": "en",
                "max": 5,
            })
            data = resp.json()
            return [
                {
                    "title": a.get("title", ""),
                    "source": a.get("source", {}).get("name", "Unknown"),
                    "url": a.get("url", ""),
                    "published_at": (a.get("publishedAt") or "")[:10],
                    "is_trusted": _is_trusted_source("", a.get("url", "")),
                }
                for a in data.get("articles", [])
                if a.get("title")
            ]
    except Exception as e:
        print(f"[NewsSearch] GNews error: {e}")
        return []


def _demo_search(query: str) -> list[dict]:
    """
    Illustrative demo results — only active when DEMO_MODE=true in .env.
    Articles are clearly marked as illustrative/demo data.
    """
    q = query.lower()
    fake_signals = ["government hiding", "secret", "leaked", "conspiracy",
                    "chemtrail", "microchip", "crisis actor", "plandemic"]
    is_likely_fake = any(s in q for s in fake_signals)

    if is_likely_fake:
        return [
            {
                "title": "[DEMO] Fact Check: No evidence supports these claims",
                "source": "Reuters Fact Check (illustrative)",
                "url": "https://reuters.com/fact-check",
                "published_at": "2025-11-14",
                "is_trusted": True,
            },
        ]
    else:
        return [
            {
                "title": f"[DEMO] Related coverage found for: '{query[:50]}...'",
                "source": "BBC News (illustrative)",
                "url": "https://bbc.com/news",
                "published_at": "2025-12-01",
                "is_trusted": True,
            },
        ]


def _build_query(text: str, claims: list[str], entities: list[dict] = None) -> str:
    """Build a concise search query from entities or claims."""
    if entities:
        # Filter for concrete nouns
        keywords = [e["text"] for e in entities if e.get("type") in ("ORG", "PERSON", "GPE", "PRODUCT", "EVENT")]
        # Unique and limited to top 3
        unique_kw = list(dict.fromkeys(keywords))[:3]
        if unique_kw:
            return " ".join(f'"{k}"' for k in unique_kw)
            
    if claims:
        # Use only the first 5-6 words of the claim so it's not too restrictive
        words = claims[0].replace('"', '').split()[:6]
        return " ".join(words)
        
    # Fallback: first few significant words of text
    words = text.replace('"', '').split()[:6]
    return " ".join(words)


def _is_trusted_source(source_id: str | None, url: str | None) -> bool:
    s_id = source_id or ""
    u = url or ""
    combined = (s_id + " " + u).lower()
    return any(s in combined for s in TRUSTED_SOURCES)


def _infer_signal(articles: list[dict], query: str) -> str:
    """
    Determine whether articles corroborate, contradict, or are absent.

    BUG FIX: Original always returned "corroborates" for any trusted article.
    Now checks article titles for debunking language first.
    """
    if not articles:
        return "not_found"

    debunk_count = 0
    corroborate_count = 0

    for a in articles:
        title = (a.get("title") or "").lower()
        is_trusted = a.get("is_trusted", False)

        if is_trusted and any(kw in title for kw in DEBUNK_KEYWORDS):
            debunk_count += 1
        elif is_trusted:
            corroborate_count += 1

    # Debunking evidence takes precedence
    if debunk_count >= 1:
        return "contradicts"
    if corroborate_count >= 1:
        return "corroborates"
    return "not_found"
