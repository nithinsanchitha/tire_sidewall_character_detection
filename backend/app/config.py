from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    data_dir: Path = Path("data")
    reference_dir: Path = Path(__file__).resolve().parents[2] / "references"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    max_upload_mb: int = 12
    max_pixels: int = 20_000_000
    ocr_gpu: bool = False
    ocr_download_enabled: bool = False
    ocr_model_dir: str = "models/easyocr"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_local_only: bool = True
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    external_base_url: str = "https://api.openai.com/v1"
    external_model: str = ""
    external_api_key: str = ""
    llm_timeout: float = 90
    retrieval_min_score: float = 0.22
settings = Settings()
