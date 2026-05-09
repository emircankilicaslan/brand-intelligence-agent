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
(async BFS)     (async batch)   (instaloader)   (Claude API)
   │              │
   ▼              ▼
PageContent[]  raw images
   │              │
   │          Deduplicator (pHash)
   │              │
   │          FashionClassifier (CLIP / heuristic)
   │              │
   │          VisualClusterer (CLIP embeddings + KMeans)
   │              │
   └──────────────┼─────────────────┐
                  ▼                 ▼
            ColorExtractor     TextAnalyzer (Claude API)
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

## Trade-offs

| Decision | Upside | Downside |
|---|---|---|
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

## Operationalising for Thousands of Brands

- Wrap the agent in a task queue (Celery + Redis or AWS SQS). Each brand config is a message.
- Store outputs in object storage (S3/GCS) keyed by `brand_slug/run_id/`.
- Run CLIP inference on GPU instances via batch inference endpoint (Replicate or a self-hosted Triton server) — the bottleneck at scale is not I/O but embedding computation.
- Cache pages and images in a CDN-backed content store to avoid re-downloading unchanged assets.
- Parameterise Claude calls for cost control: cheaper models for first-pass synthesis, expensive models only for the positioning statement and cluster descriptions.
- Observability: ship structured logs (already in place) to a log aggregator; emit per-brand metrics (image count, pages crawled, time taken) to a timeseries store for SLA monitoring.
