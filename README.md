# NLP Project 2: Website Question Answering Model

This project is model-only (no backend server required). It provides:
- Website text collection (scraping)
- Cleaning + chunking + metadata extraction
- Hybrid retrieval (Dense embeddings + BM25)
- Two QA modes:
  - Extractive QA (lightweight BERT-like model for fast local runs)
  - Generative QA (Gemini API, using `GEMINI_API_KEY` from `.env`)

## Project Structure

```text
web-QA/
├── data/
│   ├── raw/
│   ├── processed/
│   ├── index/
│   └── seed_urls.txt
├── scripts/
│   ├── run_model.py
│   └── run_model.sh
├── src/
│   └── webqa/
│       ├── config.py
│       ├── pipeline.py
│       ├── preprocessing.py
│       ├── qa.py
│       ├── retrieval.py
│       └── scraping.py
└── requirements.txt
```

## Setup

```bash
# Use Python 3.13 (recommended) or 3.12 for best compatibility.
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` at project root:

```bash
GEMINI_API_KEY=your_key_here
# Optional: set true if your machine has valid local CA certs.
WEBQA_VERIFY_SSL=false
# Optional: if true, use local fallback model when Gemini fails/quota is exhausted.
WEBQA_ENABLE_LOCAL_FALLBACK=false
```

### If You See PyO3 / tokenizers / pydantic-core Build Errors

Those errors usually mean your environment is using Python 3.14, while some Rust-backed wheels in the NLP stack are not fully available for 3.14 yet.

Recreate the environment with Python 3.13:

```bash
rm -rf .venv
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Run Model (No Backend)

```bash
bash scripts/run_model.sh --ingest
```

Ask in extractive mode:

```bash
bash scripts/run_model.sh --question "What is the main topic?" --mode extractive --top-k 4
```

Ask in generative mode (Gemini):

```bash
bash scripts/run_model.sh --question "Summarize homepage content" --mode generative --top-k 4
```

By default, generative mode does not download a local fallback model.
If you want fallback generation when Gemini quota is exhausted, set `WEBQA_ENABLE_LOCAL_FALLBACK=true`.

Use a custom URL list file:

```bash
bash scripts/run_model.sh --ingest --urls-file data/seed_urls.txt
```
