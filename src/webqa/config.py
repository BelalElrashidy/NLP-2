from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    raw_pages_path: Path = Path("data/raw/pages.json")
    chunks_path: Path = Path("data/processed/chunks.jsonl")
    faiss_index_path: Path = Path("data/index/chunks.index")
    metadata_path: Path = Path("data/index/metadata.pkl")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    extractive_model: str = "sshleifer/tiny-distilbert-base-cased-distilled-squad"
    gemini_model: str = "gemini-2.5-flash"
    chunk_size: int = 180
    chunk_overlap: int = 40
    crawl_max_pages: int = 500
    crawl_max_depth: int = 3


SETTINGS = Settings()
