# Composio Toolkit Audit — 100 Apps

Fresh start: only `data/apps.json` is filled in. Run the pipeline to generate results, analysis, verification, and the HTML case study.

## What you need

1. Python 3.10+
2. A Composio API key → [app.composio.dev](https://app.composio.dev) → Settings → API Keys

Put it in `.env` (copy from `.env.example`):

```
COMPOSIO_API_KEY=ak_your_key_here
```

## Step-by-step

Open a terminal in this folder:

```bash
cd composio-research
```

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your API key

```bash
# Windows PowerShell
copy .env.example .env
# then edit .env and paste your key

# macOS / Linux
cp .env.example .env
```

### 3. Research all 100 apps (~3–5 min)

```bash
python agent/research_agent.py
```

Writes `data/results.json`. Optional smoke test first:

```bash
python agent/research_agent.py --limit 5
```

### 4. Cluster patterns

```bash
python agent/analyze.py
```

Writes `data/analysis.json` (auth / gating / blockers + headline).

### 5. Verify a sample

```bash
python agent/verify.py
```

Re-fetches ~25 apps independently, scores accuracy, corrects misses. Writes `data/verification_log.json`.

### 6. Build the case-study page

```bash
python scripts/build_page.py
```

Writes `output/case-study.html` — open that file in a browser.

---

## One-shot alternative

After steps 1–2:

```bash
python scripts/run_all.py
```

That runs research → analyze → verify → build page in order.

## What each step produces

| Step | Output |
|------|--------|
| research | `data/results.json` |
| analyze | `data/analysis.json` |
| verify | `data/verification_log.json` (+ corrections in results) |
| build | `output/case-study.html` |
