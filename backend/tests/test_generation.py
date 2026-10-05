import asyncio
import json
import httpx
from app.generation import Generator
from app.config import Settings
from app.schemas import TireFields, Citation


def test_offline_returns_evidence():
    g = Generator(Settings(ollama_base_url="http://127.0.0.1:1", llm_timeout=0.1))
    c = Citation(
        chunk_id="c1", document="ref.txt", page=None, text="R is radial.", score=0.8
    )
    reply = asyncio.run(g.answer(TireFields(), "What is R?", [c], []))
    assert not reply.generated and reply.citations == [c]
    assert not asyncio.run(g.health())["ready"]


def test_citation_validation(monkeypatch):
    response = {"answer": "R means radial [c1].", "citation_ids": ["c1"]}

    class Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, *a, **kw):
            return httpx.Response(
                200,
                json={"message": {"content": json.dumps(response)}},
                request=httpx.Request("POST", "http://test"),
            )

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    c = Citation(
        chunk_id="c1", document="ref.txt", page=None, text="R is radial.", score=0.8
    )
    g = Generator(Settings())
    r = asyncio.run(g.answer(TireFields(), "R?", [c], []))
    assert r.generated
    response.update(answer="Incorrect [invented].", citation_ids=["invented"])
    assert not asyncio.run(g.answer(TireFields(), "R?", [c], [])).generated
