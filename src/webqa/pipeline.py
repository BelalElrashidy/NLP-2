from dataclasses import dataclass

from .config import SETTINGS
from .preprocessing import build_chunks, load_chunks_jsonl, save_chunks_jsonl
from .qa import ExtractiveQA, GenerativeQA
from .retrieval import HybridRetriever, RetrievalResult
from .scraping import collect_pages, save_pages


@dataclass
class PipelineAnswer:
    answer: str
    confidence: float | None
    sources: list[RetrievalResult]


class WebsiteQAPipeline:
    def __init__(self) -> None:
        self.settings = SETTINGS
        self.retriever: HybridRetriever | None = None
        self.extractive_qa: ExtractiveQA | None = None
        self.generative_qa: GenerativeQA | None = None

    def ingest(self, urls: list[str], timeout_seconds: int, chunk_size: int, chunk_overlap: int) -> tuple[int, int, int]:
        pages = collect_pages(urls=urls, timeout_seconds=timeout_seconds)
        if not pages:
            raise ValueError("No pages were collected from the provided URLs.")
        save_pages(self.settings.raw_pages_path, pages)

        chunks = build_chunks(pages=pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if not chunks:
            raise ValueError("No text chunks were created from collected pages.")
        save_chunks_jsonl(self.settings.chunks_path, chunks)

        retriever = HybridRetriever(embedding_model=self.settings.embedding_model)
        retriever.build(chunks)
        retriever.save(self.settings.faiss_index_path, self.settings.metadata_path)
        self.retriever = retriever

        return len(pages), len(chunks), len(chunks)

    def _ensure_retriever(self) -> HybridRetriever:
        if self.retriever is None:
            self.retriever = HybridRetriever.load(
                index_path=self.settings.faiss_index_path,
                metadata_path=self.settings.metadata_path,
            )
        return self.retriever

    def _ensure_extractive(self) -> ExtractiveQA:
        if self.extractive_qa is None:
            self.extractive_qa = ExtractiveQA(self.settings.extractive_model)
        return self.extractive_qa

    def _ensure_generative(self) -> GenerativeQA:
        if self.generative_qa is None:
            self.generative_qa = GenerativeQA(self.settings.gemini_model)
        return self.generative_qa

    def ask(self, question: str, mode: str = "extractive", top_k: int = 4) -> PipelineAnswer:
        retriever = self._ensure_retriever()
        retrieved = retriever.retrieve(question, top_k=top_k)
        contexts = [r.chunk.text for r in retrieved]

        if mode == "extractive":
            extractive = self._ensure_extractive()
            answer, score = extractive.answer(question=question, contexts=contexts)
            return PipelineAnswer(answer=answer, confidence=score, sources=retrieved)

        generative = self._ensure_generative()
        answer = generative.answer(question=question, contexts=contexts)
        return PipelineAnswer(answer=answer, confidence=None, sources=retrieved)

    def stats(self) -> dict[str, int]:
        chunks = load_chunks_jsonl(self.settings.chunks_path)
        unique_urls = {chunk.url for chunk in chunks}
        return {"chunks": len(chunks), "sources": len(unique_urls)}
