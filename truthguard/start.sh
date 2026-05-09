#!/bin/bash
# ─────────────────────────────────────────────
# TruthGuard — One-Click Setup & Run Script
# ─────────────────────────────────────────────
set -e

echo ""
echo "🛡️  TruthGuard — Setting up backend..."
echo "──────────────────────────────────────"

# Navigate to backend
cd "$(dirname "$0")/backend"

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
  echo "📦 Creating Python virtual environment..."
  python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install/upgrade dependencies
echo "⬇️  Installing dependencies (this may take a minute first time)..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Download spaCy model if not present
echo "🧠 Checking spaCy language model..."
python3 -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null || \
  python3 -m spacy download en_core_web_sm --quiet

# Pre-download the HuggingFace fake-news model (so first request isn't slow)
echo "🤖 Pre-loading fake news classifier model..."
python3 -c "
from transformers import pipeline
try:
    pipe = pipeline('text-classification', model='hamzab/roberta-fake-news-classification')
    print('  ✅ hamzab/roberta-fake-news-classification ready')
except Exception as e:
    print(f'  ⚠️  Primary model unavailable ({e}) — will try fallback on startup')
" 2>/dev/null || echo "  ℹ️  Model will be downloaded on first request."

echo ""
echo "✅ Setup complete!"
echo "──────────────────────────────────────"
echo "🚀 Starting TruthGuard API on http://localhost:8000"
echo "📖 API docs: http://localhost:8000/docs"
echo "🌐 Frontend: open truthguard/frontend/index.html in your browser"
echo ""
echo "💡 Tip: Add your API keys to backend/.env for live news search"
echo "   and Gemini AI explanations. See .env for key registration links."
echo "──────────────────────────────────────"
echo ""

# Start the server
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
