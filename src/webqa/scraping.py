import json
import os
import re
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

import certifi
import requests
import urllib3
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import asyncio


@dataclass
class PageDocument:
    url: str
    title: str
    headers: list[str]
    paragraphs: list[str]


ALLOWED_DOMAIN_SUFFIXES = ("islamweb.net",)
BLOCKED_HOST_PREFIXES = ("audio.",)


def _page_allowed(url: str) -> bool:
    parts = urlsplit(url)
    hostname = (parts.hostname or "").lower()
    path = parts.path.lower()

    if hostname.startswith(BLOCKED_HOST_PREFIXES):
        return False

    if hostname == "fatwatok.islamweb.net":
        if parts.query and re.search(r"(?:^|&)id=\d{4,8}(?:&|$)", parts.query):
            return True
        return parts.path in {"", "/"}

    if hostname.endswith("islamweb.net"):
            # Allow only specific content page patterns with actual IDs (no listing pages)
            # Match patterns like /ar/article/12345/ or /ar/article/12345/slug or /ar/fatwa/12345
            article_match = re.match(r'^/ar/article/\d+', path)
            fatwa_match = re.match(r'^/ar/fatwa/\d+', path)
            return bool(article_match or fatwa_match)

    return False



def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[\u200f\u200e\xa0]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_noise_paragraph(text: str) -> bool:
    """Return True if a paragraph looks like boilerplate/navigation/footer noise."""
    if not text:
        return True
    # short content is usually noise
    words = text.split()
    if len(words) < 6:
        return True

    lower = text.lower()
    noise_markers = [
        "المزيد",
        "جميع الحقوق",
        "عربي",
        "español",
        "deutsch",
        "français",
        "english",
        "indonesia",
        "copyright",
        "©",
    ]
    for m in noise_markers:
        if m in lower:
            return True

    # repetitive short symbols or purely numeric lines
    if re.match(r"^[^\w\u0600-\u06FF]{3,}$", text):
        return True

    return False


def _normalize_url(url: str, base_url: str | None = None) -> str | None:
    resolved = urljoin(base_url, url) if base_url else url
    parts = urlsplit(resolved)

    if parts.scheme not in {"http", "https"}:
        return None

    if not parts.netloc:
        return None

    if parts.hostname is None:
        return None

    query_items = parse_qsl(parts.query, keep_blank_values=True)
    normalized_query = urlencode(sorted(query_items), doseq=True)
    normalized_parts = parts._replace(fragment="", query=normalized_query, netloc=parts.netloc.lower())
    return urlunsplit(normalized_parts)


def _host_allowed(hostname: str, allowed_suffixes: Iterable[str]) -> bool:
    hostname = hostname.lower()
    if hostname.startswith(BLOCKED_HOST_PREFIXES):
        return False
    return any(hostname == suffix or hostname.endswith(f".{suffix}") for suffix in allowed_suffixes)


def _extract_links(html: str, base_url: str, allowed_suffixes: Iterable[str]) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for tag in soup.select("a[href]"):
        href = tag.get("href", "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:")):
            continue

        normalized = _normalize_url(href, base_url=base_url)
        if normalized is None:
            continue

        hostname = urlsplit(normalized).hostname or ""
        if _host_allowed(hostname, allowed_suffixes) and _page_allowed(normalized):
            links.append(normalized)

    return links


def _extract_fatwa_ids(text: str) -> list[str]:
    ids: set[str] = set()

    for match in re.findall(r"(?:\?|&)id=(\d{4,8})", text):
        ids.add(match)

    for match in re.findall(r"/fatwa/(\d{4,8})", text):
        ids.add(match)

    for match in re.findall(r"\b(\d{5,6})\b", text):
        ids.add(match)

    return sorted(ids)


def _fetch_response(url: str, timeout_seconds: int = 20) -> requests.Response | None:
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
        if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1"}:
            response.encoding = response.apparent_encoding
    except requests.RequestException:
        return None

    return response


async def _fetch_with_playwright(url: str, timeout_seconds: int = 20) -> str | None:
    """Fetch a page using Playwright to render JavaScript content."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=timeout_seconds * 1000, wait_until="networkidle")
            content = await page.content()
            await browser.close()
            return content
    except Exception:
        return None


def _fetch_response_playwright(url: str, timeout_seconds: int = 20) -> requests.Response | None:
    """Fetch fatwatok pages with Playwright, return as requests.Response-like object."""
    html_content = asyncio.run(_fetch_with_playwright(url, timeout_seconds))
    if html_content is None:
        return None
    
    class FakeResponse:
        def __init__(self, text):
            self.text = text
            self.status_code = 200
    
    return FakeResponse(html_content)


def fetch_page(url: str, timeout_seconds: int = 20) -> PageDocument | None:
    response = _fetch_response(url, timeout_seconds=timeout_seconds)
    if response is None:
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript", "iframe", "svg", "img"]):
        tag.extract()

    title = _clean_text(soup.title.get_text()) if soup.title else "Untitled"

    header_tags = soup.select("h1, h2, h3, h4, h5, h6")
    headers = [_clean_text(tag.get_text()) for tag in header_tags if _clean_text(tag.get_text())]

    content_tags = soup.select("p, li")
    paragraphs = [_clean_text(tag.get_text()) for tag in content_tags if _clean_text(tag.get_text())]
    # filter out navigation/footer noise
    paragraphs = [p for p in paragraphs if not _is_noise_paragraph(p)]

    if not paragraphs:
        body_text = _clean_text(soup.get_text(" "))
        paragraphs = [body_text] if body_text else []

    return PageDocument(url=url, title=title, headers=headers[:40], paragraphs=paragraphs)


def _extract_article_text(soup: BeautifulSoup) -> tuple[str, list[str]]:
    article_title = soup.select_one(".articletitle")
    article_body = soup.select_one(".articletxt")
    title_text = _clean_text(article_title.get_text(" ")) if article_title else ""

    if article_body:
        paragraphs = [_clean_text(p.get_text()) for p in article_body.select("p") if _clean_text(p.get_text())]
        if paragraphs:
            return title_text, paragraphs

        body_text = _clean_text(article_body.get_text(" "))
        if body_text:
            return title_text, [body_text]

    if title_text:
        return title_text, []

    candidates = []
    for sel in ("div.article", "div.article-body", "div.content", "div#content", "main", "article"):
        for tag in soup.select(sel):
            text = _clean_text(tag.get_text(" "))
            if len(text.split()) > 40:
                candidates.append(text)

    if candidates:
        longest = max(candidates, key=lambda t: len(t))
        parts = [p.strip() for p in re.split(r"\n{1,}|\.\s+", longest) if p.strip()]
        return title_text, [p for p in parts if len(p.split()) > 10]

    return title_text, []


def _extract_fatwatok_content(soup: BeautifulSoup) -> tuple[str, list[str]]:
    """
    Extract fatwatok title and answer from the rendered page.
    With Playwright rendering, the page should have proper class-based structure.
    """
    title = ""
    paragraphs = []

    # Try class-based selectors (now reliable after Playwright rendering)
    title_elem = soup.select_one(".card-title_text")
    if title_elem:
        title = _clean_text(title_elem.get_text(" "))

    answer_elem = soup.select_one(".card-answer")
    if answer_elem:
        # Extract paragraphs from the answer block
        for p in answer_elem.select("p"):
            text = _clean_text(p.get_text(" "))
            if text and len(text.split()) > 4:
                paragraphs.append(text)
        
        # If no paragraphs found with <p> tags, fall back to text extraction
        if not paragraphs:
            text = _clean_text(answer_elem.get_text(" "))
            if text and len(text.split()) > 4:
                paragraphs = [text]

    return title, paragraphs


def collect_pages(
    urls: list[str],
    timeout_seconds: int = 20,
    max_pages: int = 1000,
    max_depth: int = 6,
    throttle_every: int = 20,
    sleep_seconds: int = 5,
) -> list[PageDocument]:
    if not urls:
        return []

    allowed_suffixes = set(ALLOWED_DOMAIN_SUFFIXES)

    queue: deque[tuple[str, int]] = deque()
    seen_urls: set[str] = set()
    docs: list[PageDocument] = []
    skipped_count = 0
    fetch_count = 0

    def _log(message: str) -> None:
        print(message, flush=True)

    for url in urls:
        normalized = _normalize_url(url)
        if normalized is None or not _page_allowed(normalized):
            _log(f"[crawl] seed skipped: {url}")
            continue
        _log(f"[crawl] seed queued: {normalized}")
        queue.append((normalized, 0))
        seen_urls.add(normalized)

    while queue and len(docs) < max_pages:
        current_url, depth = queue.popleft()
        _log(f"[crawl] fetching depth={depth} url={current_url}")
        
        # Use Playwright for fatwatok pages (JavaScript-rendered), requests for others
        if "fatwatok" in current_url.lower() and "?id=" in current_url.lower():
            _log(f"[crawl] fetch mode=playwright url={current_url}")
            response = _fetch_response_playwright(current_url, timeout_seconds=timeout_seconds)
        else:
            _log(f"[crawl] fetch mode=requests url={current_url}")
            response = _fetch_response(current_url, timeout_seconds=timeout_seconds)
        if response is None:
            _log(f"[crawl] fetch failed url={current_url}")
            continue

        fetch_count += 1
        if throttle_every > 0 and fetch_count % throttle_every == 0:
            _log(f"[crawl] throttle sleep={sleep_seconds}s after {fetch_count} fetches")
            time.sleep(sleep_seconds)

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe", "svg", "img"]):
            tag.extract()

        title = _clean_text(soup.title.get_text()) if soup.title else "Untitled"
        header_tags = soup.select("h1, h2, h3, h4, h5, h6")
        headers = [_clean_text(tag.get_text()) for tag in header_tags if _clean_text(tag.get_text())]

        lower_url = current_url.lower()

        paragraphs = []
        if "fatwatok" in lower_url and "?id=" in lower_url:
            faq_title, faq_paragraphs = _extract_fatwatok_content(soup)
            if faq_title:
                title = faq_title
            paragraphs = faq_paragraphs
        elif "/article/" in lower_url or "/articles/" in lower_url:
            article_title, article_paragraphs = _extract_article_text(soup)
            if article_title:
                title = article_title
            paragraphs = article_paragraphs

        if not paragraphs:
            content_tags = soup.select("p, li")
            paragraphs = [_clean_text(tag.get_text()) for tag in content_tags if _clean_text(tag.get_text())]

        # filter noise (applies to extracted article/fatwa fallbacks and list pages)
        paragraphs = [p for p in paragraphs if not _is_noise_paragraph(p)]

        if not paragraphs:
            body_text = _clean_text(soup.get_text(" "))
            paragraphs = [body_text] if body_text else []

        current_host = urlsplit(current_url).hostname or ""
        if not _host_allowed(current_host, allowed_suffixes):
            _log(f"[crawl] host blocked url={current_url}")
            continue

        is_fatwatok_non_id = "fatwatok" in lower_url and "?id=" not in lower_url
        if not is_fatwatok_non_id and paragraphs:
            doc = PageDocument(url=current_url, title=title, headers=headers[:40], paragraphs=paragraphs)
            docs.append(doc)
            _log(f"[crawl] saved url={current_url} title={title!r} paragraphs={len(paragraphs)} docs={len(docs)}")
        else:
            _log(f"[crawl] skipped save url={current_url} paragraphs={len(paragraphs)}")

        if depth >= max_depth:
            _log(f"[crawl] max depth reached url={current_url}")
            continue

        for link in _extract_links(response.text, current_url, allowed_suffixes):
            if link not in seen_urls:
                seen_urls.add(link)
                queue.append((link, depth + 1))
                _log(f"[crawl] queued link depth={depth + 1} url={link}")

        if "fatwatok" in current_url:
            for fatwa_id in _extract_fatwa_ids(response.text):
                fatwa_url = f"https://fatwatok.islamweb.net/?id={fatwa_id}"
                if fatwa_url not in seen_urls and _page_allowed(fatwa_url):
                    seen_urls.add(fatwa_url)
                    queue.append((fatwa_url, depth + 1))
                    _log(f"[crawl] queued fatwa id={fatwa_id} url={fatwa_url}")

    return docs


def save_pages(path: Path, pages: list[PageDocument]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump([asdict(page) for page in pages], f, ensure_ascii=False, indent=2)


def load_pages(path: Path) -> list[PageDocument]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [PageDocument(**item) for item in data]
