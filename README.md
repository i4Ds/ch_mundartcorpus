# CH Mundart Corpus CSV Export

Quick converter for the CHMK free XML subcorpus.

## What this repo contains

- Source ZIP: `data/XML-CHMK_v2.2_free_subcorpus.zip`
- Unpacked XML files: `data/unpacked/XML-CHMK_v2.2_free_subcorpus/`
- Export script: `main.py`

## What is not pushed

Processed CSV output is excluded from Git with:

- `data/processed/*`

So you can regenerate locally but keep the repo size small.

## Run

```bash
uv run main.py
```

This creates:

- `data/processed/chmk_sentences.csv`
- `data/processed/chmk_overview.csv`

## CSV content

- `chmk_sentences.csv`: readable sentence-level rows (`source`, `year`, inferred `canton`, sentence text, etc.)
- `chmk_overview.csv`: one row per XML source with sentence counts, sorted by year
