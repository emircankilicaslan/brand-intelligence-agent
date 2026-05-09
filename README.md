# Brand Intelligence Agent

Autonomously produces a structured Brand DNA dossier — color palette, visual clusters, brand voice, audience signals — for any fashion brand, given only a name, URL, and optional Instagram handle.

---

## Quick Start

### Requirements

- Python 3.11+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### Install

```bash
git clone <repo>
cd brand-intelligence-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Run

```bash
python main.py configs/acne_studios.json
```

The report is written to `outputs/acne_studios/acne_studios_brand_dna.pdf`.

---

## Docker

```bash
docker build -t brand-agent .
docker run --rm \
  -v $(pwd)/configs:/app/configs \
  -v $(pwd)/outputs:/app/outputs \
  -e ANTHROPIC_API_KEY=your_key_here \
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

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for brand voice synthesis |
| `REQUEST_TIMEOUT` | 30 | HTTP timeout in seconds |
| `REQUEST_DELAY_MS` | 800 | Delay between requests (ms) |
| `MAX_CONCURRENT_REQUESTS` | 4 | Parallel image download workers |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |

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

---

## Known Limitations

- Single-page applications (React, Next.js) that render product listings client-side may yield fewer images than expected. A Playwright fallback would address this.
- Instagram collection is rate-sensitive. A session cookie or Playwright-based scraper would improve reliability.
- CLIP model weights (~600MB) are downloaded on first run. Subsequent runs use the local cache.
- PDF image quality is capped at the source resolution; very low-quality original images will appear soft in the report.
- The agent assumes a stable network. Transient failures are retried once via aiohttp redirects; persistent failures are skipped with a log entry.
