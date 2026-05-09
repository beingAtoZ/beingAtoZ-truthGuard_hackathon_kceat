"""
NLP Service — preprocessing, entity extraction, claim extraction, sentiment.
Uses spaCy for NER and enriched heuristics for claim detection.

Improvements:
  - Expanded CLAIM_PATTERNS to capture plain news phrasing (passive voice,
    attribution, quotes, statistics, event reporting)
  - Added more nuanced sentiment word lists
  - Returns word_count and avg_sentence_length for pipeline use
"""
import re
from typing import Optional

# Lazy-load spaCy model to avoid slow startup
_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = False  # Mark as unavailable
    return _nlp

# ── Clickbait / emotion signals ──
CLICKBAIT_WORDS = [
    "shocking", "you won't believe", "mind-blowing", "insane",
    "jaw-dropping", "secret", "they don't want you to know",
    "this changes everything", "breaking:", "urgent:", "alert:",
    "you need to see this", "share before deleted", "watch before banned",
    "what they're hiding", "the truth about", "never before seen",
]
HIGH_EMOTION_WORDS = [
    "outrage", "furious", "terrifying", "devastating", "unbelievable",
    "bombshell", "explosive", "scandal", "hoax", "exposed", "banned",
    "coverup", "conspiracy", "crisis", "catastrophe", "leaked",
    "nightmare", "shocking", "horrifying", "alarming", "disgraceful",
]

# ── Expanded claim extraction patterns ──
# Covers: attribution, statistics, passive-voice events, quotes,
#         official announcements, research citations, denials
CLAIM_PATTERNS = [
    # Research / scientific citation
    r"(?i)(studies?\s+show|research\s+(shows?|finds?|suggests?|indicates?)|scientists?\s+(say|found|confirm|warn|report))",
    # Attribution / source reporting
    r"(?i)(according\s+to|reported\s+by|sources?\s+(say|claim|allege)|officials?\s+(say|confirm|deny|announce|warn))",
    # Statistics and numbers
    r"(?i)(\d+\s?%|\d+[\.,]\d+\s?%|\d+\s+(million|billion|thousand|hundred)\s+(people|cases|deaths?|dollars?))",
    # Passive-voice event reporting
    r"(?i)(was\s+(arrested|killed|banned|caught|fired|confirmed|reported|found|charged|indicted|sentenced))",
    # Government / authority actions
    r"(?i)(government\s+(hid|lied|covered up|banned|approved|rejected|announced|confirmed|denied))",
    # Direct quotes or statements
    r"(?i)(said\s+in\s+a\s+statement|told\s+(reporters|journalists|media|the\s+press)|in\s+an\s+interview)",
    # Policy / legal language
    r"(?i)(new\s+(law|bill|policy|regulation|guidelines?)\s+(passed|signed|approved|rejected|introduced))",
    # Health / medical claims
    r"(?i)(vaccine|treatment|drug|medication|therapy)\s+(causes?|prevents?|cures?|linked\s+to|associated\s+with)",
    # Election / political
    r"(?i)(election\s+(results?|fraud|rigged|confirmed)|vote\s+(count|recount|certified))",
    # Denials / corrections
    r"(?i)(denies?|denied|refutes?|debunked|no\s+evidence\s+(for|of|that)|false\s+claim)",
]

def preprocess_and_extract(text: str) -> dict:
    """Extract NLP features: entities, claims, sentiment, signals."""
    text_lower = text.lower()
    clean_text = re.sub(r'\s+', ' ', text).strip()

    # ── Entity extraction via spaCy ──
    entities = []
    nlp = _get_nlp()
    if nlp:
        try:
            doc = nlp(clean_text[:5000])  # Cap for speed
            seen = set()
            for ent in doc.ents:
                if ent.label_ in ("PERSON", "ORG", "GPE", "NORP", "EVENT", "LAW", "DATE") \
                        and ent.text not in seen:
                    entities.append({"text": ent.text, "type": ent.label_})
                    seen.add(ent.text)
        except Exception:
            pass

    # ── Claim extraction via expanded regex ──
    claims = []
    # Split on sentence boundaries more robustly
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', clean_text)
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 20 or len(sent) > 400:
            continue
        for pattern in CLAIM_PATTERNS:
            if re.search(pattern, sent):
                if sent not in claims:
                    claims.append(sent)
                break
    claims = claims[:5]  # Top 5 claims

    # ── Sentiment via extended keyword heuristic ──
    positive_words = [
        "good", "great", "positive", "hope", "success", "benefit", "safe",
        "confirmed", "true", "accurate", "correct", "progress", "improvement",
        "recovery", "growth", "effective", "approved", "safe", "proven"
    ]
    negative_words = [
        "bad", "danger", "threat", "fake", "false", "lie", "corrupt", "crisis",
        "attack", "fraud", "scam", "hoax", "wrong", "failed", "disaster",
        "collapse", "outbreak", "death", "kill", "ban", "illegal", "criminal"
    ]
    pos = sum(text_lower.count(w) for w in positive_words)
    neg = sum(text_lower.count(w) for w in negative_words)

    if neg > pos + 2:
        sentiment = "negative"
    elif pos > neg + 2:
        sentiment = "positive"
    else:
        sentiment = "neutral"

    # ── Signal flags ──
    is_clickbait = any(kw in text_lower for kw in CLICKBAIT_WORDS)
    high_emotion = sum(1 for kw in HIGH_EMOTION_WORDS if kw in text_lower) >= 2

    # ── Structural signals ──
    sentences_list = re.split(r'[.!?]+', clean_text)
    sentence_count = max(len([s for s in sentences_list if s.strip()]), 1)
    word_count = len(clean_text.split())
    avg_sentence_length = word_count / sentence_count

    return {
        "clean_text": clean_text,
        "entities": entities,
        "claims": claims,
        "sentiment": sentiment,
        "is_clickbait": is_clickbait,
        "high_emotion": high_emotion,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": round(avg_sentence_length, 1),
    }
