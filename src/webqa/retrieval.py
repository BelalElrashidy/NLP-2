import pickle
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from .preprocessing import TextChunk


@dataclass
class RetrievalResult:
    chunk: TextChunk
    score: float


class HybridRetriever:
    def __init__(self, embedding_model: str) -> None:
        self.embedding_model_name = embedding_model
        self.embedder = SentenceTransformer(embedding_model)
        self.index: faiss.Index | None = None
        self.bm25: BM25Okapi | None = None
        self.chunks: list[TextChunk] = []
        self._tokenized_corpus: list[list[str]] = []

    def build(self, chunks: list[TextChunk]) -> None:
        if not chunks:
            raise ValueError("Cannot build retrieval index from empty chunks.")

        self.chunks = chunks
        self._tokenized_corpus = [chunk.text.lower().split() for chunk in chunks]
        self.bm25 = BM25Okapi(self._tokenized_corpus)

        embeddings = self.embedder.encode([c.text for c in chunks], convert_to_numpy=True)
        embeddings = embeddings.astype("float32")
        faiss.normalize_L2(embeddings)

        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)
        self.index = index

    def save(self, index_path: Path, metadata_path: Path) -> None:
        if self.index is None or self.bm25 is None:
            raise ValueError("Index has not been built yet.")

        index_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, str(index_path))
        with metadata_path.open("wb") as f:
            pickle.dump(
                {
                    "embedding_model_name": self.embedding_model_name,
                    "chunks": self.chunks,
                    "tokenized_corpus": self._tokenized_corpus,
                },
                f,
            )

    @classmethod
    def load(cls, index_path: Path, metadata_path: Path) -> "HybridRetriever":
        with metadata_path.open("rb") as f:
            data = pickle.load(f)

        retriever = cls(embedding_model=data["embedding_model_name"])
        retriever.chunks = data["chunks"]
        retriever._tokenized_corpus = data["tokenized_corpus"]
        retriever.bm25 = BM25Okapi(retriever._tokenized_corpus)
        retriever.index = faiss.read_index(str(index_path))
        return retriever

    def retrieve(self, question: str, top_k: int = 6, alpha: float = 0.25) -> list[RetrievalResult]:
        if self.index is None or self.bm25 is None:
            raise ValueError("Retriever is not initialized. Run ingest first.")

        query_embedding = self.embedder.encode([question], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(query_embedding)
        dense_scores, dense_indices = self.index.search(query_embedding, top_k)

        bm25_scores = np.array(self.bm25.get_scores(question.lower().split()), dtype=np.float32)
        if bm25_scores.max() > 0:
            bm25_scores = bm25_scores / bm25_scores.max()

        results: dict[int, float] = {}
        for score, idx in zip(dense_scores[0], dense_indices[0]):
            if idx >= 0:
                results[idx] = float(alpha * score)

        # Widen BM25 candidate pool so keyword-relevant chunks aren't missed
        bm25_top_k = top_k * 3
        for idx in np.argsort(bm25_scores)[-bm25_top_k:]:
            prev = results.get(int(idx), 0.0)
            results[int(idx)] = prev + float((1 - alpha) * bm25_scores[idx])

        ranked = sorted(results.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [RetrievalResult(chunk=self.chunks[idx], score=score) for idx, score in ranked]
