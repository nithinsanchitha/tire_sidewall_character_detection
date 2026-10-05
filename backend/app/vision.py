import io
import threading
from typing import Protocol
import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from .schemas import Detection
class SetupError(RuntimeError): pass
class VisionModel(Protocol):
    def recognize(self, image: np.ndarray) -> list[Detection]: ...
def decode_image(raw: bytes, content_type: str, max_pixels: int):
    jpeg = raw.startswith(b"\xff\xd8\xff")
    png = raw.startswith(b"\x89PNG\r\n\x1a\n")
    webp = raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
    expected = "image/jpeg" if jpeg else "image/png" if png else "image/webp" if webp else None
    if not expected or content_type != expected:
        raise ValueError("Use a valid JPEG, PNG or WebP file whose signature matches its MIME type.")
    try:
        with Image.open(io.BytesIO(raw)) as im:
            w, h = im.size
            if min(w,h) < 32 or w*h > max_pixels: raise ValueError("Image dimensions must be at least 32px per side and within the configured pixel limit.")
            if getattr(im, "n_frames", 1) > 1: raise ValueError("Animated images are not supported.")
            im.load()
            # Preserve the pixel coordinate system; do not silently EXIF-rotate.
            rgb = np.asarray(im.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Image cannot be decoded safely.") from exc

def preprocess(image, rotation=0, contrast=True, crop=None):
    h,w = image.shape[:2]
    x,y,cw,ch = crop if crop else (0,0,w,h)
    if min(x,y) < 0 or min(cw,ch) < 32 or x+cw > w or y+ch > h:
        raise ValueError("Crop is outside the image or smaller than 32 pixels.")
    work = image[y:y+ch,x:x+cw].copy()
    # Forward mapping: original -> crop -> quarter-turn rotation.
    base = np.array([[1,0,-x],[0,1,-y],[0,0,1]],dtype=float)
    if rotation == 90:
        work=cv2.rotate(work,cv2.ROTATE_90_CLOCKWISE)
        rot=np.array([[0,-1,ch-1],[1,0,0],[0,0,1]],float)
    elif rotation == 180:
        work=cv2.rotate(work,cv2.ROTATE_180)
        rot=np.array([[-1,0,cw-1],[0,-1,ch-1],[0,0,1]],float)
    elif rotation == 270:
        work=cv2.rotate(work,cv2.ROTATE_90_COUNTERCLOCKWISE)
        rot=np.array([[0,1,0],[-1,0,cw-1],[0,0,1]],float)
    else: rot=np.eye(3)
    if contrast:
        lab=cv2.cvtColor(work,cv2.COLOR_BGR2LAB)
        lab[:,:,0]=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(lab[:,:,0])
        work=cv2.cvtColor(lab,cv2.COLOR_LAB2BGR)
    return work,np.linalg.inv(rot @ base)
def map_detections(detections, inverse):
    return [d.model_copy(update={"polygon":[(inverse @ np.array([p[0],p[1],1.]))[:2].tolist() for p in d.polygon]}) for d in detections]
class EasyOCRModel:
    def __init__(self, settings):
        self.settings=settings; self.reader=None; self.lock=threading.RLock(); self.error=None
    def load(self):
        with self.lock:
            if self.reader is None:
                try:
                    import easyocr
                    self.reader=easyocr.Reader(["en"],gpu=self.settings.ocr_gpu,model_storage_directory=self.settings.ocr_model_dir,download_enabled=self.settings.ocr_download_enabled,verbose=False)
                    self.error=None
                except Exception as exc:
                    self.error="EasyOCR unavailable. Install requirements and run scripts/download_models.py before analyzing images."
                    raise SetupError(self.error) from exc
    def recognize(self,image):
        self.load()
        with self.lock:
            results=self.reader.readtext(image,detail=1,paragraph=False)
        return [Detection(text=t,confidence=float(c),polygon=np.asarray(b,dtype=float).tolist()) for b,t,c in results]
