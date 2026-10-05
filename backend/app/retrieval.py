import hashlib
import io
import threading
import numpy as np
from pypdf import PdfReader
from .schemas import Citation
from .vision import SetupError


class Retriever:
    def __init__(self, store, settings):
        self.store = store
        self.settings = settings
        self.model = None
        self.index = None
        self.rows = []
        self.lock = threading.RLock()
        self.error = None

    def load(self):
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(
                    self.settings.embedding_model,
                    local_files_only=self.settings.embedding_local_only,
                )
            except Exception as exc:
                self.error = "Embedding model unavailable. Run scripts/download_models.py to cache all-MiniLM-L6-v2."
                raise SetupError(self.error) from exc

    def _index(self, rows):
        self.load()
        import faiss

        if not rows:
            return None
        vectors = np.asarray(
            self.model.encode([r["text"] for r in rows], normalize_embeddings=True),
            dtype="float32",
        )
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        return index

    def rebuild(self):
        with self.lock:
            rows = self.store.chunks()
            index = self._index(rows)
            self.rows, self.index = rows, index
            self.error = None

    def ingest(self, raw, name, mime, source_url=None):
        if mime == "application/pdf":
            if not raw.startswith(b"%PDF-"):
                raise ValueError("PDF signature does not match.")
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported.")
            if len(reader.pages) > 200:
                raise ValueError("PDF exceeds 200-page limit.")
            pages = [
                (i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)
            ]
        elif mime == "text/plain":
            pages = [(None, raw.decode("utf-8"))]
        else:
            raise ValueError("Use a UTF-8 TXT or text-based PDF document.")
        digest = hashlib.sha256(raw).hexdigest()[:16]
        chunks = []
        for page, text in pages:
            text = " ".join(text.split())
            if len(text) > 1_000_000:
                raise ValueError("Extracted page is too large.")
            for start in range(0, len(text), 700):
                excerpt = text[start : start + 900]
                if excerpt.strip():
                    chunks.append(
                        dict(
                            id=f"{digest}-{page or 0}-{start}",
                            document=name,
                            page=page,
                            text=excerpt,
                            source_url=source_url,
                        )
                    )
        if not chunks:
            raise ValueError(
                "Document has no extractable text; scanned PDF OCR is not implemented."
            )
        # Build the complete replacement index before committing metadata.
        with self.lock:
            existing = self.store.chunks()
            known = {r["id"] for r in existing}
            new = [r for r in chunks if r["id"] not in known]
            rows = sorted(existing + new, key=lambda r: r["id"])
            index = self._index(rows)
            self.store.add_chunks(new)
            self.rows, self.index = rows, index
            self.error = None
        return len(new)

    def search(self, query, k=5):
        with self.lock:
            if self.index is None:
                self.rebuild()
            if self.index is None:
                return []
            vector = np.asarray(
                self.model.encode([query], normalize_embeddings=True), dtype="float32"
            )
            scores, ids = self.index.search(vector, min(k, len(self.rows)))
            return [
                Citation(
                    chunk_id=self.rows[i]["id"],
                    document=self.rows[i]["document"],
                    page=self.rows[i]["page"],
                    text=self.rows[i]["text"],
                    source_url=self.rows[i]["source_url"],
                    score=float(score),
                )
                for score, i in zip(scores[0], ids[0])
                if i >= 0 and score >= self.settings.retrieval_min_score
            ]
