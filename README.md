# Brand Intelligence Agent

Autonomously produces a structured Brand DNA dossier — color palette, visual clusters, brand voice, audience signals — for any fashion brand, given only a name, URL, and optional Instagram handle.

---

## Quick Start

### Requirements

- Python 3.11+
<<<<<<< HEAD
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
=======
- A Groq API key (free, no credit card) → [console.groq.com](https://console.groq.com)
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)

### Install

```bash
git clone <repo>
cd brand-intelligence-agent
<<<<<<< HEAD
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
=======
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)
```

### Run

```bash
python main.py configs/acne_studios.json
```

<<<<<<< HEAD
The report is written to `outputs/acne_studios/acne_studios_brand_dna.pdf`.
=======
Report is written to `outputs/acne_studios/acne_studios_brand_dna.pdf`.
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)

---

## Docker

```bash
docker build -t brand-agent .
docker run --rm \
  -v $(pwd)/configs:/app/configs \
  -v $(pwd)/outputs:/app/outputs \
<<<<<<< HEAD
  -e ANTHROPIC_API_KEY=your_key_here \
=======
  -e GROQ_API_KEY=your_key_here \
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)
  brand-agent configs/acne_studios.json
```

---

## Configuration

Each brand is a JSON file. No code changes required.

```json
{
  "brand_name": "Acne Studios",
  "website_url": "https://www.acnestudios.com",
  "social_handles": {
    "instagram": "acnestudios"
  },
  "crawl_depth": 2,
  "max_images": 150,
  "min_resolution": 512,
  "output_dir": "outputs/acne_studios"
}
```

| Field | Default | Description |
|---|---|---|
| `brand_name` | required | Display name used in the report |
| `website_url` | required | Brand homepage — crawl starts here |
| `social_handles.instagram` | `null` | Instagram username (without @) |
| `crawl_depth` | 2 | How many link-hops from the homepage to follow |
| `max_images` | 150 | Cap on fashion images kept after filtering |
| `min_resolution` | 512 | Minimum px on the shorter side |
| `output_dir` | `outputs` | Where images, metadata, and PDF are written |

Environment variables (`.env`):

<<<<<<< HEAD
| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for brand voice synthesis |
| `REQUEST_TIMEOUT` | 30 | HTTP timeout in seconds |
| `REQUEST_DELAY_MS` | 800 | Delay between requests (ms) |
| `MAX_CONCURRENT_REQUESTS` | 4 | Parallel image download workers |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |
=======
| Variable | Description |
|---|---|
| `GROQ_API_KEY` | **Recommended.** Free LLM for brand voice synthesis. Get at console.groq.com |
| `ANTHROPIC_API_KEY` | Optional fallback. Paid Anthropic API |
| `REQUEST_TIMEOUT` | HTTP timeout in seconds (default: 30) |
| `REQUEST_DELAY_MS` | Delay between page requests in ms (default: 800) |
| `MAX_CONCURRENT_REQUESTS` | Parallel image download workers (default: 4) |
| `LOG_LEVEL` | DEBUG / INFO / WARNING / ERROR (default: INFO) |

---

## LLM Priority

The agent tries LLM providers in this order:

1. **Groq** (`GROQ_API_KEY`) — free, fast, llama3-70b. Recommended.
2. **Ollama** (`http://localhost:11434`) — local, free, requires `ollama serve` running.
3. **Anthropic Claude** (`ANTHROPIC_API_KEY`) — paid fallback.

If none are available, visual analysis (images, colors, clusters) still runs fully. Only the textual synthesis sections (brand voice, audience, positioning) are skipped.
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)

---

## Output

```
outputs/brand_name/
├── images/                  # downloaded, filtered fashion images
├── image_metadata.json      # per-image record (URL, page context, cluster, phash)
├── text_corpus.json         # crawled page text + Instagram captions
└── brandname_brand_dna.pdf  # the Brand DNA report
```

---

## Tests

```bash
pytest tests/ -v
```

Tests cover: config loading, deduplication (exact and distinct), color palette extraction, page type classification, domain checking, image URL extraction, and PDF generation smoke test.

---

<<<<<<< HEAD
## Dependencies

| Library | Purpose |
|---|---|
| aiohttp | Async HTTP crawling and image download |
| beautifulsoup4 / lxml | HTML parsing |
| Pillow | Image loading, resize, format conversion |
| imagehash | Perceptual hash deduplication |
| transformers (CLIP) | Fashion classification + visual embeddings |
| scikit-learn | KMeans clustering + color clustering |
| anthropic | Brand voice and visual identity synthesis |
| reportlab | PDF generation |
| instaloader | Instagram caption and image collection |
| structlog | Structured logging |
| pydantic | Config validation |
| click | CLI |

---

## Anti-bot, Rate Limiting, and ToS

- Requests use a realistic browser `User-Agent` string.
- A configurable delay (`REQUEST_DELAY_MS`, default 800ms) is inserted between page fetches to avoid hammering servers.
- Concurrent image downloads are capped at `MAX_CONCURRENT_REQUESTS` (default 4).
- Instagram collection uses `instaloader` in public, unauthenticated mode. Instagram rate limits will cause the collector to log a warning and continue without social data — the agent does not crash.
- If any site returns 403/429 or blocks crawling, the agent logs the failure and processes whatever was successfully collected. It does not attempt to circumvent blocks.
- Operators are responsible for ensuring their use of this tool complies with the ToS of any site they run it against.
=======
## Anti-bot, Rate Limiting, and ToS

**Request pacing:** A configurable delay (`REQUEST_DELAY_MS`, default 800ms) is inserted between every page fetch. Concurrent image downloads are capped at `MAX_CONCURRENT_REQUESTS` (default 4). Both values are tunable per run.

**User-Agent:** All requests use a realistic desktop browser User-Agent string to avoid trivial bot detection.

**Instagram:** The agent uses `instaloader` in public, unauthenticated mode.

- Instagram enforces aggressive rate limits (HTTP 429) on unauthenticated scraping — typically after 10–15 profile requests within a short window.
- When a 429 is received, the agent logs `instagram_collection_failed` with the reason and **continues without Instagram data** rather than crashing. The PDF is still produced from website data alone.
- The log entry explicitly documents the failure: `reason=429 Too Many Requests handle=<handle>`.
- Mitigation options (not implemented by default, documented for transparency): authenticated sessions via `instaloader` session files; rotating residential proxies; exponential backoff with jitter. These are out of scope for the current implementation but are the natural next step for production use.

**ToS:** Operators are responsible for ensuring their use of this tool complies with the terms of service of any site they run it against. The agent is designed to be a polite crawler — it does not attempt to circumvent explicit blocks.
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)

---

## Known Limitations

<<<<<<< HEAD
- Single-page applications (React, Next.js) that render product listings client-side may yield fewer images than expected. A Playwright fallback would address this.
- Instagram collection is rate-sensitive. A session cookie or Playwright-based scraper would improve reliability.
- CLIP model weights (~600MB) are downloaded on first run. Subsequent runs use the local cache.
- PDF image quality is capped at the source resolution; very low-quality original images will appear soft in the report.
- The agent assumes a stable network. Transient failures are retried once via aiohttp redirects; persistent failures are skipped with a log entry.
=======
- Single-page applications (React, Next.js) that render content client-side may yield fewer images. A Playwright fallback would address this.
- Instagram collection is rate-sensitive in unauthenticated mode. A session cookie significantly improves reliability.
- CLIP model weights (~600MB) are downloaded on first run and cached locally.
- The agent assumes a stable network. Transient failures are retried once; persistent failures are skipped with a structured log entry.
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)
