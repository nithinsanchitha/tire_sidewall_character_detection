"""Real OCR + embedding/FAISS + persistence + offline LLM checks. Requires downloaded weights."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from fastapi.testclient import TestClient
from app.api import create_app
from app.config import Settings
import tempfile

with tempfile.TemporaryDirectory() as directory:
    settings = Settings(data_dir=Path(directory), ollama_base_url="http://127.0.0.1:1")
    with TestClient(create_app(settings)) as client:
        with open("data/synthetic-ocr-smoke.png", "rb") as image:
            r = client.post(
                "/api/scans",
                files={"file": ("SYNTHETIC-smoke.png", image, "image/png")},
            )
        assert r.status_code == 201, r.text
        scan = r.json()
        print("OCR:", scan["raw_text"])
        doc = client.post(
            "/api/documents",
            files={
                "file": (
                    "integration-reference.txt",
                    b"Project-authored integration reference. R denotes radial tire construction.",
                    "text/plain",
                )
            },
        )
        assert doc.status_code == 201 and doc.json()["chunks_added"] == 1, doc.text
        import io
        from reportlab.pdfgen.canvas import Canvas

        buf = io.BytesIO()
        pdf = Canvas(buf)
        pdf.drawString(
            20, 700, "Project-authored reference: R denotes radial tire construction."
        )
        pdf.save()
        doc = client.post(
            "/api/documents",
            files={
                "file": ("integration-reference.pdf", buf.getvalue(), "application/pdf")
            },
        )
        assert doc.status_code == 201 and doc.json()["chunks_added"] == 1, doc.text
        evidence = client.app.state.retriever.search(
            "R denotes radial tire construction", k=10
        )
        assert any(
            c.document == "integration-reference.pdf" and c.page == 1 for c in evidence
        )
        assert scan["fields"]["width_mm"] == 205, scan["fields"]
        assert scan["detections"] and scan["references"]
        assert all(
            0 <= p[0] <= scan["width"] and 0 <= p[1] <= scan["height"]
            for d in scan["detections"]
            for p in d["polygon"]
        )
        id = scan["id"]
        assert (
            client.patch(
                f"/api/scans/{id}", json=scan["fields"] | {"brand": "TOYO"}
            ).status_code
            == 200
        )
        answer = client.post(
            f"/api/scans/{id}/chat", json={"question": "Explain radial tire size"}
        ).json()
        assert not answer["generated"] and answer["citations"]
        assert client.get("/api/scans").json()["total"] == 1
        assert client.delete(f"/api/scans/{id}").status_code == 204
        print(
            "PASS real synthetic OCR, PDF/TXT ingestion, embeddings, retrieval, boxes, corrections, history, offline generation and deletion."
        )
