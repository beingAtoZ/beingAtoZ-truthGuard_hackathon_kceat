"""
Routes — /api/analyze/text, /api/analyze/url, /api/analyze/image
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from services.pipeline import run_pipeline
from services.scraper import scrape_url
from services.image_service import extract_text_from_image
import io

router = APIRouter()

class TextRequest(BaseModel):
    text: str

class URLRequest(BaseModel):
    url: str

@router.post("/analyze/text")
async def analyze_text(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    result = await run_pipeline(text=req.text, source_url=None, input_type="text")
    return result

@router.post("/analyze/url")
async def analyze_url(req: URLRequest):
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    scraped = await scrape_url(req.url)
    if not scraped.get("text"):
        raise HTTPException(status_code=422, detail="Could not extract text from URL")
    result = await run_pipeline(
        text=scraped["text"],
        source_url=req.url,
        input_type="url",
        title=scraped.get("title", ""),
        domain=scraped.get("domain", "")
    )
    return result

@router.post("/analyze/image")
async def analyze_image(file: UploadFile = File(...)):
    contents = await file.read()
    extracted_text = extract_text_from_image(io.BytesIO(contents))
    if not extracted_text.strip():
        raise HTTPException(status_code=422, detail="No readable text found in image")
    result = await run_pipeline(
        text=extracted_text,
        source_url=None,
        input_type="image"
    )
    result["ocr_text"] = extracted_text[:500]
    return result
