# Architecture Document — Brand Intelligence Agent

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI (main.py)                        │
│                  click-based entry point                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               Orchestrator (agent/orchestrator.py)          │
│   Coordinates the full pipeline; owns error boundaries      │
└──┬──────────────┬──────────────┬───────────────┬────────────┘
   │              │              │               │
   ▼              ▼              ▼               ▼
WebsiteCrawler  ImageDownloader InstagramColl.  TextAnalyzer
(async BFS)     (async batch)   (instaloader)   (Groq/Ollama/Claude)
   │              │
   ▼              ▼
PageContent[]  raw images on disk
   │              │
   │          Deduplicator (pHash, Hamming ≤ 8)
   │              │
   │          FashionClassifier (CLIP zero-shot / heuristic fallback)
   │              │
   │          VisualClusterer (CLIP embeddings + KMeans)
   │              │
   └──────────────┼─────────────────┐
                  ▼                 ▼
            ColorExtractor     TextAnalyzer (LLM)
                  │                 │
                  └────────┬────────┘
                           ▼
                     BrandDNA dataclass
                           │
                           ▼
                     PDFGenerator (reportlab)
                           │
                           ▼
                    {brand}_brand_dna.pdf
```

## Key Design Decisions

### 1. Site-agnostic crawling
The crawler uses breadth-first traversal with no hardcoded selectors. Page type classification (product, about, blog, lookbook, FAQ) is done by URL path pattern matching against a regex dictionary — any brand site maps to these types without per-domain logic. Image extraction handles `src`, `data-src`, `data-lazy-src`, and `srcset` to cover lazy-loading patterns across modern e-commerce stacks.

### 2. Resolution threshold: 512px minimum on the shorter side
512px is the standard minimum for CLIP (ViT-B/32 native resolution is 224px, but the model is pre-trained on 224–336px crops from larger images). Images below 512px on the shorter side are either UI chrome, decorative thumbnails, or resolution-degraded and add noise to downstream embeddings. Going higher (800px+) rejects valid product thumbnails on image-heavy sites. 512px is the published sweet spot for CLIP downstream tasks.

### 3. Perceptual hashing for deduplication
URL/MD5 deduplication misses the same image served from multiple CDN paths, resized thumbnails, and re-compressed variants. pHash (imagehash library) captures visual similarity across these cases. A Hamming distance threshold of ≤ 8 removes near-identical images while preserving genuinely different shots that happen to share a background or model.

### 4. Two-stage fashion classification
**Primary:** CLIP zero-shot classification against 12 candidate labels (positive: clothing/garment/model/lookbook/shoes/accessories; negative: logo/UI/landscape/food). No training data or fashion-specific fine-tuning required — generalises to any brand aesthetic.
**Fallback:** Keyword heuristic on alt text, surrounding page text, and source URL. Activates when transformers is unavailable (e.g. resource-constrained CI environments). Sufficient to maintain pipeline operation with lower precision.

### 5. LLM provider cascade for text synthesis
Three providers in priority order:
1. **Groq** (free, llama3-70b-8192, ~200ms latency) — recommended for default use
2. **Ollama** (local, llama3.2, zero cost, requires local install and disk space)
3. **Anthropic Claude** (paid, highest quality, used as fallback)

If none are reachable, visual analysis runs in full and only textual synthesis sections are marked unavailable. This preserves the pipeline's ability to deliver partial value under any configuration.

Why not a single provider? Cost, availability, and user constraints vary. A cascade approach makes the agent deployable in constrained environments (no API budget, air-gapped, etc.) without code changes.

### 6. CLIP embeddings + KMeans for visual clustering
CLIP projects images into a semantically meaningful 512-dimensional space — similar styling, colour, and subject matter cluster naturally without any fashion-specific labels. KMeans then groups these into 3–5 clusters (set dynamically as `floor(n_images / 20)`, clamped to 3–5). This avoids trivially small or oversized clusters that come from fixed counts on variable image sets.

### 7. Async collection with configurable pacing
Both the crawler and image downloader are fully async (aiohttp + asyncio). A semaphore caps concurrent requests at `MAX_CONCURRENT_REQUESTS` (default 4). A per-request sleep of `REQUEST_DELAY_MS` (default 800ms) is inserted between page fetches. Both values are configurable in `.env` — operators can tune for speed vs. politeness depending on the target site.

### 8. Graceful failure at every stage
Each major stage (website crawl, image download, Instagram, LLM synthesis) is wrapped in try/except. Failures are logged as structured events with `[warning]` or `[error]` level and the pipeline continues. A brand with a blocked Instagram and an LLM outage still produces a valid PDF with visual data. This was a deliberate design choice: partial value is always better than a crash.

### 9. Instagram rate limiting — design decision and mitigation
`instaloader` is used in unauthenticated public mode. Instagram enforces hard rate limits on unauthenticated access (typically HTTP 429 after 10–15 requests). The agent:
- Logs the 429 with structured context: `instagram_collection_failed reason=429 handle=<handle>`
- Skips Instagram and continues with website data
- Documents this explicitly in README under anti-bot measures

Production mitigations (not implemented, documented for transparency):
- **Session authentication:** `instaloader` supports session file injection — a logged-in session raises the rate limit significantly
- **Exponential backoff with jitter:** retry after randomised delays
- **Rotating proxies:** residential IP rotation to distribute requests
These are natural next iterations for high-volume use.

## Trade-offs

| Decision | Upside | Downside |
|---|---|---|
| CLIP zero-shot | No training data, brand-agnostic | Lower precision than fine-tuned model |
| Groq as default LLM | Free, fast, no credit card | Rate limits at high volume |
| BFS crawler | Simple, predictable | Misses JS-rendered product listings |
| No Playwright | Simpler, faster | Misses React/Next.js shops |
| instaloader | No API key needed | Fragile to Instagram rate limits |
| pHash dedup | Catches CDN/size variants | Can miss semantically duplicate shoots |

## What Would Change With More Time

**Higher priority:**

1. **Playwright integration** — Many DTC brands use Next.js or Shopify Hydrogen. A headless browser fallback in `WebsiteCrawler` would recover these. The architecture has a clean injection point: the crawler returns `PageContent[]` regardless of fetch method.

2. **Fine-tuned fashion classifier** — A lightweight ViT trained on DeepFashion2 would give precise garment-level labels (not binary fashion/non-fashion), producing richer garment mix data. The `FashionClassifier` class is designed for drop-in replacement.

3. **Instagram session auth** — Injecting a session cookie via instaloader raises the practical rate limit from ~15 to hundreds of posts per run. One `.env` variable (`INSTAGRAM_SESSION_FILE`) would be sufficient.

4. **Vector-store deduplication** — At 10k+ images, pHash iteration becomes slow. FAISS or Qdrant over CLIP embeddings would replace it with sub-linear lookup.

5. **Structured caching** — Re-running against the same brand should skip already-downloaded images. A SQLite store keyed by URL hash would cut second-run time by ~80%.

## Operationalising for Thousands of Brands

- Wrap the agent in a task queue (Celery + Redis or AWS SQS). Each brand config is a message.
- Store outputs in object storage (S3/GCS) keyed by `brand_slug/run_id/`.
- Move CLIP inference to a GPU batch endpoint (Replicate or self-hosted Triton) — at scale, embedding computation dominates over I/O.
- Cache pages and images in a content-addressed store to avoid re-downloading unchanged assets across runs.
- Parameterise LLM calls for cost control: Groq for first-pass synthesis, Claude only for final positioning statements where quality matters most.
- Ship structured logs (already in place via structlog) to a log aggregator; emit per-brand metrics (image count, pages crawled, run duration) to a time-series store for SLA monitoring.
