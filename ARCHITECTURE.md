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
<<<<<<< HEAD
(async BFS)     (async batch)   (instaloader)   (Claude API)
   │              │
   ▼              ▼
PageContent[]  raw images
   │              │
   │          Deduplicator (pHash)
   │              │
   │          FashionClassifier (CLIP / heuristic)
=======
(async BFS)     (async batch)   (instaloader)   (Groq/Ollama/Claude)
   │              │
   ▼              ▼
PageContent[]  raw images on disk
   │              │
   │          Deduplicator (pHash, Hamming ≤ 8)
   │              │
   │          FashionClassifier (CLIP zero-shot / heuristic fallback)
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)
   │              │
   │          VisualClusterer (CLIP embeddings + KMeans)
   │              │
   └──────────────┼─────────────────┐
                  ▼                 ▼
<<<<<<< HEAD
            ColorExtractor     TextAnalyzer (Claude API)
=======
            ColorExtractor     TextAnalyzer (LLM)
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)
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
<<<<<<< HEAD
The crawler uses a breadth-first strategy with no hardcoded selectors. Page type classification (product, about, blog, lookbook, etc.) is done purely by URL path pattern matching. Image extraction handles `src`, `data-src`, `data-lazy-src`, and `srcset` attributes to cover most lazy-loading patterns. This makes the agent work on any site structure without per-domain code.

### 2. Resolution threshold: 512px minimum on the shorter side
512px is the standard minimum for CLIP (224px native, but pre-trained on 224–336px crops of larger images). Any image smaller than this either adds noise to embeddings or is decorative UI chrome. Going higher (e.g. 800px) would reject valid product thumbnails. 512px is the documented sweet spot in the CLIP paper for downstream tasks.

### 3. Perceptual hashing for deduplication
MD5 / URL dedup misses the same image served from different CDN paths. pHash (imagehash library) captures visual similarity — identical or near-identical crops are treated as duplicates (Hamming distance ≤ 8). This removes CDN variants, re-compressed versions, and thumbnail/full-size pairs of the same shot.

### 4. Two-stage fashion classification
Primary: CLIP zero-shot classification against 12 label candidates. This works on any image without any fashion-specific fine-tuning and generalises to new brand aesthetics. Fallback (when CLIP is unavailable): keyword heuristic on alt text, surrounding text, and page URL — sufficient to keep the pipeline functional in constrained environments.

### 5. Claude for text synthesis
Sentence-level NLP (spaCy, NLTK) would surface keywords but not brand voice nuance. Claude's language understanding produces genuinely useful output — tone descriptions, value extraction, positioning statements — that a non-technical brand strategist can use directly. The tradeoff is API cost and latency; both are acceptable given this runs once per brand. GPT-4 was considered but Anthropic's API is used throughout the project already (consistency, single billing).

### 6. CLIP embeddings + KMeans for visual clustering
No fashion-specific labelling needed. CLIP embeddings project images into a semantically meaningful 512-d space; KMeans then groups visually coherent shots. Cluster count (3–6) is set dynamically based on image count (floor(n/20), clamped to 3–5). This avoids the trivially small or large clusters that come from fixed counts.

### 7. Async collection
Both the crawler and image downloader are fully async (aiohttp + asyncio). A configurable semaphore limits concurrency to avoid triggering rate limits. Sleep between requests is configurable via `REQUEST_DELAY_MS`. This respects site constraints while staying efficient.

### 8. Graceful failure everywhere
Each major collection stage (website, Instagram, download) is wrapped in a try/except that logs the error and continues rather than crashing. The agent can produce a valid (if partial) report even if Instagram is blocked or a site returns 403 for some pages.
=======
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
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)

## Trade-offs

| Decision | Upside | Downside |
|---|---|---|
<<<<<<< HEAD
| CLIP zero-shot | No training data needed, brand-agnostic | Lower precision than fine-tuned model |
| Claude for synthesis | High-quality natural language | API cost per run |
| BFS crawler | Simple, predictable | May miss SPA-rendered content |
| No Playwright/JS rendering | Simpler, faster, no browser install | Misses some React/Next.js shops |
| instaloader | Simple, no API key needed | Fragile to Instagram rate limits |

## What Would Change With More Time

**Higher priority with more time:**

1. **Playwright integration for JS-heavy sites** — Many fashion brands (especially DTC) use Next.js or Shopify hydrogen. A headless browser fallback would recover these sites. The current architecture has a clean injection point in `WebsiteCrawler`.

2. **Fine-tuned fashion classifier** — Training a lightweight ViT or EfficientNet on DeepFashion2 categories would give precise garment-level labels (not just binary fashion/non-fashion), producing richer category mix data.

3. **Vector store for image deduplication at scale** — pHash works well up to ~10k images. At scale, approximate nearest-neighbour (FAISS or Qdrant) over CLIP embeddings would replace it.

4. **Streaming PDF generation** — For brands with 500+ images, the current in-memory approach would strain RAM. A streaming PDF writer or tile-based image loading would be needed.

5. **Structured caching layer** — Re-running against the same brand should skip already-downloaded images and re-use cached text. A SQLite-backed content store (keyed by URL hash) would cut second-run time by 80%.

6. **Multi-source social** — TikTok and Pinterest carry different visual signals than Instagram. A unified social adapter interface is already implied by the `SocialHandles` model.
=======
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
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)

## Operationalising for Thousands of Brands

- Wrap the agent in a task queue (Celery + Redis or AWS SQS). Each brand config is a message.
- Store outputs in object storage (S3/GCS) keyed by `brand_slug/run_id/`.
<<<<<<< HEAD
- Run CLIP inference on GPU instances via batch inference endpoint (Replicate or a self-hosted Triton server) — the bottleneck at scale is not I/O but embedding computation.
- Cache pages and images in a CDN-backed content store to avoid re-downloading unchanged assets.
- Parameterise Claude calls for cost control: cheaper models for first-pass synthesis, expensive models only for the positioning statement and cluster descriptions.
- Observability: ship structured logs (already in place) to a log aggregator; emit per-brand metrics (image count, pages crawled, time taken) to a timeseries store for SLA monitoring.
=======
- Move CLIP inference to a GPU batch endpoint (Replicate or self-hosted Triton) — at scale, embedding computation dominates over I/O.
- Cache pages and images in a content-addressed store to avoid re-downloading unchanged assets across runs.
- Parameterise LLM calls for cost control: Groq for first-pass synthesis, Claude only for final positioning statements where quality matters most.
- Ship structured logs (already in place via structlog) to a log aggregator; emit per-brand metrics (image count, pages crawled, run duration) to a time-series store for SLA monitoring.
>>>>>>> 40aa1e8 (feat: Brand Intelligence Agent — autonomous fashion brand DNA analysis)
