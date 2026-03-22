import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import certifi
import requests
import urllib3
from bs4 import BeautifulSoup


@dataclass
class PageDocument:
    url: str
    title: str
    headers: list[str]
    paragraphs: list[str]


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[\u200f\u200e\xa0]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_page(url: str, timeout_seconds: int = 20) -> PageDocument | None:
    verify_ssl = os.getenv("WEBQA_VERIFY_SSL", "false").lower() == "true"
    verify_arg = certifi.where() if verify_ssl else False
    if not verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            verify=verify_arg,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript", "iframe", "svg", "img"]):
        tag.extract()

    title = _clean_text(soup.title.get_text()) if soup.title else "Untitled"

    header_tags = soup.select("h1, h2, h3, h4, h5, h6")
    headers = [_clean_text(tag.get_text()) for tag in header_tags if _clean_text(tag.get_text())]

    content_tags = soup.select("p, li")
    paragraphs = [_clean_text(tag.get_text()) for tag in content_tags if _clean_text(tag.get_text())]

    if not paragraphs:
        body_text = _clean_text(soup.get_text(" "))
        paragraphs = [body_text] if body_text else []

    return PageDocument(url=url, title=title, headers=headers[:40], paragraphs=paragraphs)


def collect_pages(urls: list[str], timeout_seconds: int = 20) -> list[PageDocument]:
    docs: list[PageDocument] = []
    for url in urls:
        doc = fetch_page(url, timeout_seconds=timeout_seconds)
        if doc is not None and doc.paragraphs:
            docs.append(doc)
    return docs


def save_pages(path: Path, pages: list[PageDocument]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump([asdict(page) for page in pages], f, ensure_ascii=False, indent=2)


def load_pages(path: Path) -> list[PageDocument]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [PageDocument(**item) for item in data]
