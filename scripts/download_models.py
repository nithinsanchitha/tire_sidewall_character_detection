"""Run from repository root with the backend virtual environment activated."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.config import settings
import easyocr
from sentence_transformers import SentenceTransformer
print('Downloading pretrained EasyOCR English detector/recognizer...')
easyocr.Reader(['en'],gpu=settings.ocr_gpu,model_storage_directory=settings.ocr_model_dir,download_enabled=True,verbose=False)
print('Downloading sentence embeddings...')
SentenceTransformer(settings.embedding_model)
print('Models ready. Normal application startup does not download weights.')
