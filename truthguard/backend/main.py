"""
TruthGuard — FastAPI Backend
Entry point: uvicorn main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.analyze import router as analyze_router

app = FastAPI(
    title="TruthGuard API",
    description="AI-powered fake news detection backend",
    version="1.0.0"
)

# Allow frontend (any origin during hackathon)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "TruthGuard API"}
