#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from webqa.config import SETTINGS
from webqa.pipeline import WebsiteQAPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Website QA model without backend.")
    parser.add_argument(
        "--urls-file",
        type=Path,
        default=Path("data/seed_urls.txt"),
        help="Path to text file with one URL per line.",
    )
    parser.add_argument("--ingest", action="store_true", help="Scrape and index website content.")
    parser.add_argument("--question", type=str, default="", help="Question to ask.")
    parser.add_argument(
        "--mode",
        type=str,
        default="extractive",
        choices=["extractive", "generative"],
        help="Answering mode.",
    )
    parser.add_argument("--top-k", type=int, default=4, help="Retrieved chunks count.")
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--chunk-size", type=int, default=SETTINGS.chunk_size)
    parser.add_argument("--chunk-overlap", type=int, default=SETTINGS.chunk_overlap)
    return parser.parse_args()


def load_urls(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"URLs file not found: {path}")
    urls = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not urls:
        raise ValueError("URLs file is empty.")
    return urls


def main() -> None:
    args = parse_args()
    pipeline = WebsiteQAPipeline()

    if args.ingest:
        urls = load_urls(args.urls_file)
        try:
            pages, chunks, index_size = pipeline.ingest(
                urls=urls,
                timeout_seconds=args.timeout_seconds,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
            )
        except ValueError as exc:
            print(f"Ingestion failed: {exc}")
            raise SystemExit(1)

        print(f"Ingest complete: pages={pages}, chunks={chunks}, index={index_size}")

    if args.question:
        try:
            result = pipeline.ask(question=args.question, mode=args.mode, top_k=args.top_k)
        except FileNotFoundError:
            print("Index not found. Run ingestion first: bash scripts/run_model.sh --ingest")
            raise SystemExit(1)
        except (ValueError, RuntimeError) as exc:
            print(f"Question run failed: {exc}")
            raise SystemExit(1)

        print("\nAnswer:")
        print(result.answer)
        if result.confidence is not None:
            print(f"\nConfidence: {result.confidence:.4f}")

        print("\nSources:")
        for i, src in enumerate(result.sources, start=1):
            print(f"{i}. [{src.score:.4f}] {src.chunk.title} | {src.chunk.url}")


if __name__ == "__main__":
    main()
