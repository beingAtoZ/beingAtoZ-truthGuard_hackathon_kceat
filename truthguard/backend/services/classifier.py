"""
Classifier Service — HuggingFace transformer for fake/real classification.

Model priority (in order):
  1. hamzab/roberta-fake-news-classification  — fine-tuned on FakeNewsNet/LIAR
  2. mrm8488/bert-tiny-finetuned-fake-news     — lighter, fast fallback
  3. Heuristic classifier                      — pure rule-based, no internet

BUG FIX: The original code used 'roberta-base-openai-detector' which is an
AI-text detector (human vs GPT), NOT a fake news detector. That model's labels
(LABEL_0=human, LABEL_1=AI-generated) were incorrectly mapped to real/fake,
causing neutral human-written news to always be classified as REAL.
"""
import re
from typing import Optional

_classifier = None
_model_name_loaded = None

def _get_classifier():
    """Lazy-load the HuggingFace pipeline with correct model priority."""
    global _classifier, _model_name_loaded
    if _classifier is None:
        from transformers import pipeline

        # Priority order: best fake-news model → lighter fallback
        candidates = [
            ("hamzab/roberta-fake-news-classification",  _make_hamzab_adapter),
            ("mrm8488/bert-tiny-finetuned-fake-news",    _make_mrm_adapter),
        ]

        for model_id, adapter_fn in candidates:
            try:
                pipe = pipeline(
                    "text-classification",
                    model=model_id,
                    truncation=True,
                    max_length=512
                )
                _classifier = adapter_fn(pipe)
                _model_name_loaded = model_id
                print(f"[Classifier] Loaded {model_id}")
                break
            except Exception as e:
                print(f"[Classifier] Could not load {model_id}: {e}")

        if _classifier is None:
            print("[Classifier] All models failed — using heuristic fallback")
            _classifier = False

    return _classifier


def _make_hamzab_adapter(pipe):
    """
    hamzab/roberta-fake-news-classification outputs either:
      LABEL_0 / LABEL_1  (older versions)
      TRUE / FAKE        (current HF hosted version)
    Normalises both to pipeline-standard 'real' / 'fake'.
    """
    def _call(text):
        raw = pipe(text)[0]
        label_map = {
            # Numeric label scheme
            "LABEL_0": "fake",
            "LABEL_1": "real",
            # String label scheme (current)
            "TRUE":  "real",
            "FAKE":  "fake",
            # Lower-case variants just in case
            "true":  "real",
            "fake":  "fake",
        }
        label = label_map.get(raw["label"], raw["label"].lower())
        return {"label": label, "score": raw["score"]}
    return _call


def _make_mrm_adapter(pipe):
    """
    mrm8488/bert-tiny-finetuned-fake-news outputs:
      FAKE, REAL  (direct string labels)
    """
    def _call(text):
        raw = pipe(text)[0]
        label = raw["label"].lower()
        return {"label": label, "score": raw["score"]}
    return _call


# ── Heuristic fallback signals ──
FAKE_SIGNALS = [
    "hoax", "fake news", "conspiracy", "they don't want you", "leaked",
    "secret cure", "banned by", "mainstream media won't", "government hiding",
    "miracle cure", "explosive revelation", "shocking truth", "wake up sheeple",
    "deep state", "plandemic", "microchip", "crisis actor", "big pharma hiding",
    "one weird trick", "doctors hate", "what they won't tell you", "censored",
    "cover-up", "shadow government", "new world order", "illuminati confirmed",
]
REAL_SIGNALS = [
    "according to", "study published", "peer-reviewed", "research confirms",
    "officials say", "government announced", "reported by reuters",
    "associated press", "scientists confirm", "data shows", "statistics show",
    "survey found", "clinical trial", "confirmed by", "in a statement",
    "press conference", "official report", "published in", "journal of",
]
MISLEADING_SIGNALS = [
    "out of context", "misattributed", "outdated", "half truth",
    "cherry-picked", "misleading", "exaggerated", "old video", "old photo",
]


def classify_text(text: str) -> dict:
    """
    Returns {"label": "fake|real|misleading|unverified", "score": float 0-1}
    """
    clf = _get_classifier()
    text_input = text[:1500]  # Truncate for speed

    if clf:
        try:
            result = clf(text_input)
            label = result["label"]
            score = result["score"]

            # Refine borderline confidence into "misleading" / "unverified"
            if label == "fake" and score < 0.65:
                label = "misleading"
            elif label == "real" and score < 0.58:
                label = "unverified"

            return {"label": label, "score": score}
        except Exception as e:
            print(f"[Classifier] Inference error: {e}")

    # ── Heuristic fallback ──
    return _heuristic_classify(text_input)


def _heuristic_classify(text: str) -> dict:
    """Rule-based fallback classifier — expanded keyword lists."""
    text_lower = text.lower()

    fake_count      = sum(1 for s in FAKE_SIGNALS if s in text_lower)
    real_count      = sum(1 for s in REAL_SIGNALS if s in text_lower)
    mislead_count   = sum(1 for s in MISLEADING_SIGNALS if s in text_lower)

    # Stylistic signals
    exclamation_count = text.count("!")
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    question_count = text.count("?")

    if exclamation_count > 3:
        fake_count += 1
    if exclamation_count > 6:
        fake_count += 1
    if caps_ratio > 0.15:
        fake_count += 1
    if question_count > 4:           # Rhetorical questions → misleading
        mislead_count += 1

    # Misleading signals tilt toward misleading rather than fake
    if mislead_count >= 2:
        fake_count = max(fake_count, 1)

    total = fake_count + real_count
    if total == 0 and mislead_count == 0:
        return {"label": "unverified", "score": 0.52}

    if fake_count > real_count:
        score = min(0.95, 0.55 + (fake_count / (total + 3)) * 0.4)
        label = "fake" if score > 0.65 else "misleading"
    else:
        score = min(0.92, 0.55 + (real_count / (total + 3)) * 0.38)
        label = "real" if score > 0.63 else "unverified"

    return {"label": label, "score": score}
