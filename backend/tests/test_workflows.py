import io
import json
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.api import create_app
from app.config import Settings
from app.schemas import Detection, ChatReply, TireFields, Citation
from app.vision import SetupError, preprocess, map_detections, decode_image
from app.parsing import parse_fields
from app.retrieval import Retriever
from app.storage import Store


# Isolated tests explicitly inject doubles: no claims of real OCR or semantic accuracy.
class Vision:
    reader = True
    error = None

    def recognize(self, image):
        return [
            Detection(
                text="205/55 R16 91V",
                confidence=0.8,
                polygon=[[1, 2], [40, 2], [40, 20], [1, 20]],
            )
        ]


class Retrieval:
    rows = []
    index = True
    error = None

    def ingest(self, *args):
        return 1

    def search(self, q):
        return [
            Citation(
                chunk_id="known",
                document="test.txt",
                page=None,
                text="R means radial construction.",
                score=0.9,
            )
        ]


class Offline:
    async def health(self):
        return {"ready": False, "detail": "Offline test"}

    async def answer(self, fields, question, citations, history):
        return ChatReply(
            answer="Generated answer unavailable.", generated=False, citations=citations
        )


class Missing(Vision):
    def recognize(self, image):
        raise SetupError("Install OCR weights.")


def image_bytes():
    b = io.BytesIO()
    Image.new("RGB", (100, 80), "white").save(b, format="PNG")
    return b.getvalue()


@pytest.fixture
def client(tmp_path):
    settings = Settings(data_dir=tmp_path, reference_dir=tmp_path / "refs")
    app = create_app(settings, Vision(), Retrieval(), Offline())
    with TestClient(app) as c:
        yield c


def upload(c):
    return c.post(
        "/api/scans", files={"file": ("photo.png", image_bytes(), "image/png")}
    )


def test_scan_lifecycle_and_isolation(client):
    r = upload(client)
    assert r.status_code == 201
    r = r.json()
    id = r["id"]
    assert r["fields"]["width_mm"] == 205 and r["original_fields"]["load_index"] == 91
    assert client.get(r["image_url"]).headers["content-type"] == "image/png"
    corrected = r["fields"] | {"brand": "MICHELIN"}
    assert client.patch(f"/api/scans/{id}", json=corrected).status_code == 200
    scan = client.get(f"/api/scans/{id}").json()
    assert (
        scan["fields"]["brand"] == "MICHELIN"
        and scan["original_fields"]["brand"] is None
    )
    assert scan["correction_count"] == 1
    chat = client.post(
        f"/api/scans/{id}/chat", json={"question": "Explain size"}
    ).json()
    assert chat["generated"] is False and chat["citations"][0]["chunk_id"] == "known"
    other = upload(client).json()
    assert other["messages"] == []
    assert client.get("/api/scans?page=1&page_size=1").json()["total"] == 2
    assert client.get("/api/scans?page=2&page_size=1").json()["items"][0]["id"] == id
    assert client.delete(f"/api/scans/{id}").status_code == 204
    assert client.get(f"/api/scans/{id}").status_code == 404
    assert client.get(r["image_url"]).status_code == 404
    db = client.app.state.store.db
    assert (
        db.execute("SELECT count(*) FROM messages WHERE scan_id=?", (id,)).fetchone()[0]
        == 0
    )
    assert (
        db.execute(
            "SELECT count(*) FROM corrections WHERE scan_id=?", (id,)
        ).fetchone()[0]
        == 0
    )


def test_validation_and_cors(client):
    assert (
        client.post(
            "/api/scans", files={"file": ("bad.png", b"not png", "image/png")}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/scans", files={"file": ("a.jpg", image_bytes(), "image/jpeg")}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/scans",
            files={"file": ("a.png", image_bytes(), "image/png")},
            data={"rotation": "45"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/scans",
            files={"file": ("a.png", image_bytes(), "image/png")},
            data={"crop": "[-1,0,40,40]"},
        ).status_code
        == 422
    )
    assert client.get("/api/scans?page=0").status_code == 422
    id = upload(client).json()["id"]
    assert client.patch(f"/api/scans/{id}", json={"load_index": 999}).status_code == 422
    assert (
        client.post(f"/api/scans/{id}/chat", json={"question": " "}).status_code == 422
    )
    r = client.options(
        "/api/scans",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    r = client.options(
        "/api/scans",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in r.headers


def test_missing_model_and_upload_limit(tmp_path):
    app = create_app(
        Settings(data_dir=tmp_path, max_upload_mb=1, reference_dir=tmp_path / "refs"),
        Missing(),
        Retrieval(),
        Offline(),
    )
    with TestClient(app) as c:
        assert upload(c).status_code == 503
        assert (
            c.post(
                "/api/scans",
                files={"file": ("large.png", b"x" * 1_048_577, "image/png")},
            ).status_code
            == 413
        )


def test_parsing():
    f, w = parse_fields("MICHELIN\n205/55 R16 91V\nDOT ABCD EF 2323")
    assert (
        f.width_mm,
        f.aspect_ratio,
        f.construction,
        f.rim_inches,
        f.load_index,
        f.speed_rating,
    ) == (205, 55, "radial", 16, 91, "V")
    assert (f.manufacture_week, f.manufacture_year) == (23, 2023)
    assert parse_fields("2323")[0].manufacture_year is None
    assert parse_fields("DOT ABCD 9923")[0].manufacture_year is None
    assert parse_fields("DOT ABCD 2399")[0].manufacture_year is None
    assert parse_fields("DOT ABCD EF\n2323")[0].manufacture_year is None
    assert parse_fields("205/55 R16 91V 225/50 R17 94W")[0].width_mm is None
    assert parse_fields("999/99 R99 999Z")[0].width_mm is None
    assert parse_fields("UNKNOWN BRAND")[0].brand is None


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_box_mapping(rotation):
    image = np.zeros((120, 180, 3), dtype="uint8")
    crop = [20, 30, 80, 60]
    work, inverse = preprocess(image, rotation, False, crop)
    original = np.array([35.0, 42.0, 1.0])
    forward = np.linalg.inv(inverse)
    p = (forward @ original)[:2].tolist()
    d = Detection(text="x", polygon=[p, p, p, p], confidence=0.5)
    mapped = map_detections([d], inverse)[0]
    assert np.allclose(mapped.polygon[0], original[:2])
    # Check actual rotated pixel position, independently of matrix round-trip.
    marker = np.zeros_like(image)
    marker[42, 35] = 255
    rotated, _ = preprocess(marker, rotation, False, crop)
    y, x = np.argwhere(rotated[:, :, 0] == 255)[0]
    assert np.allclose([x, y], p)


def test_persistent_correction(tmp_path):
    s = Settings(data_dir=tmp_path, reference_dir=tmp_path / "refs")
    with TestClient(create_app(s, Vision(), Retrieval(), Offline())) as c:
        id = upload(c).json()["id"]
        c.patch(f"/api/scans/{id}", json={"brand": "TOYO"})
    with TestClient(create_app(s, Vision(), Retrieval(), Offline())) as c:
        assert c.get(f"/api/scans/{id}").json()["fields"]["brand"] == "TOYO"


class Embed:
    def encode(self, texts, normalize_embeddings=True):
        v = np.array(
            [[1.0, 0.0] if "radial" in text.lower() else [0.0, 1.0] for text in texts],
            dtype="float32",
        )
        return v


def test_txt_pdf_ingestion_real_faiss(tmp_path):
    store = Store(tmp_path / "db")
    r = Retriever(store, Settings(data_dir=tmp_path))
    r.model = Embed()
    assert r.ingest(b"R means radial construction.", "radial.txt", "text/plain") == 1
    assert r.ingest(b"R means radial construction.", "radial.txt", "text/plain") == 0
    assert r.search("radial")[0].document == "radial.txt"
    assert r.search("unrelated") == []
    # Minimal text PDF fixture generated by an optional test-only library.
    from reportlab.pdfgen.canvas import Canvas

    b = io.BytesIO()
    canvas = Canvas(b)
    canvas.drawString(20, 700, "R is radial construction.")
    canvas.save()
    assert r.ingest(b.getvalue(), "manual.pdf", "application/pdf") == 1
    assert any(c.page == 1 for c in r.search("radial"))
    assert store.chunks()[0]["id"]
    with pytest.raises(ValueError):
        r.ingest(b"", "blank.txt", "text/plain")
    store.db.close()
