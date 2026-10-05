from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
class TireFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brand: str | None = Field(None, max_length=80)
    width_mm: int | None = Field(None, ge=100, le=500)
    aspect_ratio: int | None = Field(None, ge=20, le=95)
    construction: Literal["radial", "diagonal", "belted"] | None = None
    rim_inches: int | None = Field(None, ge=10, le=30)
    load_index: int | None = Field(None, ge=50, le=150)
    speed_rating: Literal["A1","A2","A3","A4","A5","A6","A7","A8","B","C","D","E","F","G","J","K","L","M","N","P","Q","R","S","T","U","H","V","W","Y","ZR"] | None = None
    dot_code: str | None = Field(None, max_length=100)
    manufacture_week: int | None = Field(None, ge=1, le=53)
    manufacture_year: int | None = Field(None, ge=2000, le=2099)
class Detection(BaseModel):
    text: str
    confidence: float | None = Field(None, ge=0, le=1)
    polygon: list[list[float]]
class Citation(BaseModel):
    chunk_id: str
    document: str
    page: int | None
    text: str
    source_url: str | None = None
    score: float
class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
class ChatReply(BaseModel):
    answer: str
    generated: bool
    citations: list[Citation]
    warning: str | None = None
class Scan(BaseModel):
    id: str
    filename: str
    created_at: str
    image_url: str
    width: int
    height: int
    detections: list[Detection]
    raw_text: str
    original_fields: TireFields
    fields: TireFields
    parse_warnings: list[str]
    correction_count: int
    references: list[Citation]
    retrieval_warning: str | None = None
    messages: list[dict]
class ScanPage(BaseModel):
    items: list[Scan]
    total: int
    page: int
    page_size: int
