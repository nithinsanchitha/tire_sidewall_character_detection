import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager
import cv2
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from .config import settings as defaults
from .schemas import Scan, ScanPage, TireFields, ChatRequest, ChatReply
from .vision import EasyOCRModel, SetupError, decode_image, preprocess, map_detections
from .parsing import parse_fields
from .storage import Store
from .retrieval import Retriever
from .generation import Generator


def create_app(settings=defaults, vision=None, retriever=None, generator=None):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    images = settings.data_dir / "images"
    images.mkdir(exist_ok=True)
    store = Store(settings.data_dir / "tirevision.sqlite3")
    vision = vision or EasyOCRModel(settings)
    retriever = retriever or Retriever(store, settings)
    generator = generator or Generator(settings)

    def seed():
        for path in sorted(settings.reference_dir.glob("*.txt")):
            retriever.ingest(path.read_bytes(), path.name, "text/plain")

    @asynccontextmanager
    async def lifespan(app):
        try:
            await run_in_threadpool(seed)
        except SetupError:
            pass
        yield
        store.db.close()

    app = FastAPI(title="Tire Vision AI", version="1.0.0", lifespan=lifespan)
    app.state.store = store
    app.state.vision = vision
    app.state.retriever = retriever
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    async def read_upload(file):
        raw = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
        if len(raw) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, "Upload exceeds configured size limit.")
        return raw

    def retrieve(
        scan,
        question="Explain tire size, load index, speed rating and manufacturing date markings",
    ):
        try:
            if not retriever.rows:
                seed()
            scan.references = retriever.search(
                question + " " + json.dumps(scan.fields.model_dump(exclude_none=True))
            )
            scan.retrieval_warning = None
        except SetupError as e:
            scan.references = []
            scan.retrieval_warning = str(e)
        return scan

    def require(id):
        scan = store.get(id)
        if not scan:
            raise HTTPException(404, "Scan not found.")
        return scan

    @app.get("/health")
    async def health():
        llm = await generator.health()
        return {
            "status": "ok",
            "ocr": {
                "ready": vision.reader is not None,
                "detail": vision.error
                or (
                    "EasyOCR loaded"
                    if vision.reader
                    else "Not loaded; first analysis checks installed weights"
                ),
            },
            "retrieval": {
                "ready": retriever.index is not None,
                "detail": retriever.error or f"{len(retriever.rows)} indexed chunks",
            },
            "llm": llm,
            "provider": settings.llm_provider,
        }

    @app.post("/api/scans", response_model=Scan, status_code=201)
    async def analyze(
        file: UploadFile = File(...),
        rotation: int = Form(0),
        contrast: bool = Form(True),
        crop: str | None = Form(None),
    ):
        if rotation not in (0, 90, 180, 270):
            raise HTTPException(422, "Rotation must be 0, 90, 180 or 270.")
        raw = await read_upload(file)

        def process():
            try:
                image = decode_image(raw, file.content_type or "", settings.max_pixels)
                coords = json.loads(crop) if crop else None
                if coords is not None and (
                    not isinstance(coords, list)
                    or len(coords) != 4
                    or any(type(v) != int for v in coords)
                ):
                    raise ValueError(
                        "Crop must be [x,y,width,height] in original image pixels."
                    )
                work, inverse = preprocess(image, rotation, contrast, coords)
                detections = map_detections(vision.recognize(work), inverse)
                text = "\n".join(d.text for d in detections)
                fields, warnings = parse_fields(text)
                id = uuid.uuid4().hex
                h, w = image.shape[:2]
                scan = Scan(
                    id=id,
                    filename=Path(file.filename or "image").name[:200],
                    created_at=datetime.now(timezone.utc).isoformat(),
                    image_url=f"/api/scans/{id}/image",
                    width=w,
                    height=h,
                    detections=detections,
                    raw_text=text,
                    original_fields=fields,
                    fields=fields,
                    parse_warnings=warnings,
                    correction_count=0,
                    references=[],
                    messages=[],
                )
                retrieve(scan)
                if not cv2.imwrite(str(images / f"{id}.png"), image):
                    raise RuntimeError("Image could not be stored")
                try:
                    store.save(scan)
                except Exception:
                    (images / f"{id}.png").unlink(missing_ok=True)
                    raise
                return scan
            except (ValueError, TypeError) as e:
                raise HTTPException(422, str(e)) from e
            except SetupError as e:
                raise HTTPException(503, str(e)) from e

        return await run_in_threadpool(process)

    @app.get("/api/scans", response_model=ScanPage)
    def history(page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=50)):
        items, total = store.page(page, page_size)
        return ScanPage(items=items, total=total, page=page, page_size=page_size)

    @app.get("/api/scans/{scan_id}", response_model=Scan)
    def one(scan_id: str):
        return retrieve(require(scan_id))

    @app.get("/api/scans/{scan_id}/image")
    def image(scan_id: str):
        require(scan_id)
        path = images / f"{scan_id}.png"
        if not path.is_file():
            raise HTTPException(404, "Stored image missing.")
        return FileResponse(
            path, media_type="image/png", headers={"Cache-Control": "no-store"}
        )

    @app.patch("/api/scans/{scan_id}", response_model=Scan)
    def correction(scan_id: str, fields: TireFields):
        require(scan_id)
        if (fields.manufacture_week is None) != (fields.manufacture_year is None):
            raise HTTPException(
                422, "Manufacturing week and year must be supplied together."
            )
        return retrieve(store.correct(scan_id, fields))

    @app.delete("/api/scans/{scan_id}", status_code=204)
    def delete(scan_id: str):
        require(scan_id)
        store.delete(scan_id)
        (images / f"{scan_id}.png").unlink(missing_ok=True)

    @app.post("/api/scans/{scan_id}/chat", response_model=ChatReply)
    async def chat(scan_id: str, request: ChatRequest):
        if not request.question.strip():
            raise HTTPException(422, "Question cannot be blank.")
        scan = await run_in_threadpool(retrieve, require(scan_id), request.question)
        # The full conversation remains visible, but only current fields and recent user questions enter generation.
        history = [m for m in scan.messages if m["role"] == "user"][-4:]
        if scan.retrieval_warning:
            reply = ChatReply(
                answer="Reference retrieval unavailable. Install the embedding model and ingest references.",
                generated=False,
                citations=[],
                warning=scan.retrieval_warning,
            )
        else:
            reply = await generator.answer(
                scan.fields, request.question, scan.references, history
            )
        store.message(scan_id, "user", request.question)
        store.message(scan_id, "assistant", reply.answer)
        return reply

    @app.post("/api/documents", status_code=201)
    async def ingest(file: UploadFile = File(...)):
        raw = await read_upload(file)
        try:
            count = await run_in_threadpool(
                retriever.ingest,
                raw,
                Path(file.filename or "reference").name[:200],
                file.content_type or "",
            )
            return {
                "document": Path(file.filename or "reference").name,
                "chunks_added": count,
            }
        except SetupError as e:
            raise HTTPException(503, str(e)) from e
        except Exception as e:
            # Do not leak document text or parser diagnostics.
            raise HTTPException(
                422,
                "Document could not be ingested. Use an unencrypted text PDF (at most 200 pages) or UTF-8 TXT.",
            ) from e

    return app
