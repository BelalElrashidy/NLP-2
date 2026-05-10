import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .scraping import PageDocument


@dataclass
class TextChunk:
    chunk_id: str
    url: str
    title: str
    header_hint: str
    text: str


def clean_for_chunking(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def chunk_words(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    step = max(1, chunk_size - chunk_overlap)
    chunks: list[str] = []

    for start in range(0, len(words), step):
        part = words[start : start + chunk_size]
        if not part:
            continue
        chunks.append(" ".join(part))
        if start + chunk_size >= len(words):
            break
    return chunks


def build_chunks(
    pages: list[PageDocument],
    chunk_size: int = 180,
    chunk_overlap: int = 40,
    min_chunk_length: int = 20,
) -> list[TextChunk]:
    all_chunks: list[TextChunk] = []

    for page_idx, page in enumerate(pages):
        header_hint = " | ".join(page.headers[:3]) if page.headers else ""
        text = clean_for_chunking("\n".join(page.paragraphs))
        segments = chunk_words(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        for seg_idx, seg in enumerate(segments):
            # Skip chunks that are too small (noise filtering)
            if len(seg.split()) < min_chunk_length:
                continue

            all_chunks.append(
                TextChunk(
                    chunk_id=f"doc{page_idx}_chunk{seg_idx}",
                    url=page.url,
                    title=page.title,
                    header_hint=header_hint,
                    text=seg,
                )
            )

    return all_chunks


def save_chunks_jsonl(path: Path, chunks: list[TextChunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in chunks:
            f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")


def load_chunks_jsonl(path: Path) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            chunks.append(TextChunk(**json.loads(line)))
    return chunks
