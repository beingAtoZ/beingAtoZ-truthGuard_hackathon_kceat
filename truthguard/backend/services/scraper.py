"""
Web Scraper Service
Extracts article title + body text from any URL using newspaper3k.
Falls back to BeautifulSoup if newspaper3k fails.
"""
import asyncio
import re
from urllib.parse import urlparse


async def scrape_url(url: str) -> dict:
    """Scrape a URL and return {title, text, domain}."""
    return await asyncio.to_thread(_scrape_sync, url)


def _scrape_sync(url: str) -> dict:
    domain = _extract_domain(url)

    # ── Method 1: newspaper3k ──
    try:
        from newspaper import Article
        article = Article(url)
        article.download()
        article.parse()
        text = article.text.strip()
        title = article.title or ""
        if text and len(text) > 100:
            return {"title": title, "text": text, "domain": domain}
    except Exception as e:
        print(f"[Scraper] newspaper3k failed: {e}")

    # ── Method 2: BeautifulSoup fallback ──
    try:
        import httpx
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (compatible; TruthGuardBot/1.0)"}
        resp = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title else ""
        # Try article/main tags first, else body
        content = soup.find("article") or soup.find("main") or soup.find("body")
        text = content.get_text(separator=" ", strip=True) if content else ""
        text = re.sub(r'\s{2,}', ' ', text).strip()

        return {"title": title, "text": text[:8000], "domain": domain}
    except Exception as e:
        print(f"[Scraper] BeautifulSoup fallback failed: {e}")

    return {"title": "", "text": "", "domain": domain}


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""
