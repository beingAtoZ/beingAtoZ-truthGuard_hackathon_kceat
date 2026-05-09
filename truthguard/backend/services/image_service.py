"""
Image Service — OCR text extraction from uploaded images.
Uses pytesseract (Tesseract OCR engine wrapper).
Falls back to a placeholder if Tesseract not installed.
"""
import io
from PIL import Image


def extract_text_from_image(image_bytes: io.BytesIO) -> str:
    """
    Extract text from an image using Tesseract OCR.
    Returns extracted string (may be empty if no text found).
    """
    try:
        import pytesseract

        image = Image.open(image_bytes)

        # Pre-process: convert to grayscale for better OCR accuracy
        image = image.convert("L")

        # Optionally resize if very small (improves OCR accuracy)
        w, h = image.size
        if w < 800:
            scale = 800 / w
            image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        text = pytesseract.image_to_string(image, config="--psm 3")
        return text.strip()

    except ImportError:
        print("[ImageService] pytesseract not installed — returning placeholder")
        return "Image OCR not available. Please install pytesseract and Tesseract-OCR."
    except Exception as e:
        print(f"[ImageService] OCR error: {e}")
        return ""
