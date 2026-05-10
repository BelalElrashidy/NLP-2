# Website QA System - Quick Guide

## What This Project Does

This is a **Web Question Answering System** that:
1. **Scrapes** content from IslamWeb article/fatwa pages and the fatwa portal only
2. **Chunks** the text into overlapping segments
3. **Builds** a hybrid search index (dense embeddings + BM25 keywords)
4. **Answers** questions using either extractive or generative QA

## Data Sources (Restricted IslamWeb Crawl)

| Status | URL | Website |
|--------|-----|---------|
| ✅ | https://www.islamweb.net/ar/articles/ | IslamWeb articles |
| ✅ | https://fatwatok.islamweb.net/ | Fatwa portal |

**Total: 50 pages crawled**

## Data Storage Structure

```
data/
├── raw/
│   └── pages.json                    # 50 crawled pages (JSON)
├── processed/
│   └── chunks.jsonl                  # 26 text chunks (JSON Lines - 1 chunk per line)
└── index/
    ├── chunks.index                  # FAISS vector index (embeddings)
    └── metadata.pkl                  # Chunk metadata (pickle)
```

### Chunk Details
- **Total chunks**: 431
- **Chunk size**: 180 words
- **Overlap**: 40 words (for context continuity)
- **Storage format**: JSONL (one JSON object per line)

Each chunk contains:
```json
{
  "chunk_id": "doc0_chunk0",
  "url": "https://...",
  "title": "Website Title",
  "header_hint": "Section | Subsection | ...",
  "text": "180 word chunk of content..."
}
```

## Offline Dataset Export

A complete offline copy has been created:

```
📦 webqa_dataset_export_20260508_183027.zip (1.13 MB)
```

### To Use the Offline Dataset:

#### Export current data:
```bash
python scripts/export_dataset.py export
# Creates: webqa_dataset_export_YYYYMMDD_HHMMSS.zip
```

#### Restore on another machine:
```bash
# Unzip to restore all data (raw pages, chunks, index)
unzip webqa_dataset_export_20260508_183027.zip -d .
```

#### Import a specific ZIP:
```bash
python scripts/export_dataset.py import <path_to_zip>
```

## Using the QA System

### 1. Ingest Data (Scrape & Index)
```bash
python scripts/run_model.py --ingest
```

### 2. Ask Questions

#### Extractive Mode (Fast, BERT-based):
```bash
python scripts/run_model.py \
  --question "What is Al-Azhar?" \
  --mode extractive \
  --top-k 4
```

#### Generative Mode (Uses Google Gemini API):
```bash
python scripts/run_model.py \
  --question "Tell me about Egypt's tourism" \
  --mode generative \
  --top-k 4
```

### Parameters:
- `--question`: The question to ask
- `--mode`: `extractive` (default) or `generative`
- `--top-k`: Number of chunks to retrieve (default: 4)
- `--timeout-seconds`: Web scraping timeout (default: 20)
- `--max-pages`: Crawl cap for IslamWeb ingestion (default: 150)
- `--max-depth`: Crawl depth limit (default: 3)

### Setup for Generative Mode:
Create `.env` file:
```
GEMINI_API_KEY=your_api_key_here
WEBQA_VERIFY_SSL=false
WEBQA_ENABLE_LOCAL_FALLBACK=false
```

## Architecture

### Retrieval (Hybrid Approach)
1. **Dense Embeddings**: sentence-transformers/all-MiniLM-L6-v2
   - Converts text to 384-dim vectors
   - Indexed in FAISS for fast similarity search
   
2. **BM25 Ranking**: rank-bm25
   - Keyword/TF-IDF matching
   - Hybrid score = combination of both methods

### QA Models
| Mode | Model | Speed | Quality | API |
|------|-------|-------|---------|-----|
| Extractive | sshleifer/tiny-distilbert-base-cased-distilled-squad | ⚡ Fast | Good | Local |
| Generative | Google Gemini 2.0 Flash | 🔸 Medium | Excellent | API Key |

## Key Technologies
- **Web Scraping**: BeautifulSoup4, requests
- **Embeddings**: sentence-transformers
- **Vector Index**: FAISS (CPU)
- **Ranking**: rank-bm25
- **NLP Models**: Hugging Face transformers
- **Generative AI**: Google Generative AI API
- **Chunking**: Custom word-based splitting with overlap

## Performance

**Ingestion Results:**
- ⏱️ ~10-30 seconds (depends on network)
- 📄 Pages: 7
- 📦 Chunks: 26
- 🔍 Index size: 26 embeddings

**Query Speed:**
- Extractive: <1 second
- Generative: 2-5 seconds (API dependent)

## Troubleshooting

### "No index found" error
→ Run `python scripts/run_model.py --ingest` first

### SSL Certificate errors
→ Set in `.env`: `WEBQA_VERIFY_SSL=false`

### Gemini API quota exceeded
→ Set in `.env`: `WEBQA_ENABLE_LOCAL_FALLBACK=true`

### Missing packages
→ Reinstall: `pip install -r requirements.txt`

---

**Data Last Updated**: 2026-05-08
**Offline Dataset**: webqa_dataset_export_20260508_183027.zip (Ready to use!)
