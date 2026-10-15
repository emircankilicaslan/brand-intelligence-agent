Brand Intelligence Agent
Autonomously produces a structured Brand DNA dossier (color palette, visual clusters, brand voice and audience signals) for any fashion brand, given only a name, a URL and an optional Instagram handle.

How It Works
Collect: crawl the brand website (configurable depth) and, when available, public Instagram captions and images.
Filter: keep only fashion images that meet the minimum resolution, and remove duplicates with perceptual hashing.
Analyse visuals: CLIP embeddings, KMeans visual clusters and a dominant color palette.
Synthesize text: brand voice, audience and positioning, written by an LLM provider.
Report: everything is rendered into a PDF Brand DNA report.
Quick Start
Requirements
Python 3.11+
An LLM provider for the text sections (see LLM Priority). A free Groq API key (no credit card) is recommended.


Install
git clone https://github.com/emircankilicaslan/brand-intelligence-agent.git
cd brand-intelligence-agent
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

Run
python main.py configs/acne_studios.json

Docker
docker build -t brand-agent .
docker run --rm \
  -v $(pwd)/configs:/app/configs \
  -v $(pwd)/outputs:/app/outputs \
  -e GROQ_API_KEY=your_key_here \
  brand-agent configs/acne_studios.json

  Configuration
Each brand is a JSON file. No code changes required.

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
Field	Default	Description
brand_name	required	Display name used in the report
website_url	required	Brand homepage, where the crawl starts
social_handles.instagram	null	Instagram username (without @)
crawl_depth	2	How many link hops from the homepage to follow
max_images	150	Cap on fashion images kept after filtering
min_resolution	512	Minimum px on the shorter side
output_dir	outputs	Where images, metadata and the PDF are written
Environment variables (.env):

Variable	Description
GROQ_API_KEY	Recommended. Free LLM for brand voice synthesis. Get one at console.groq.com
ANTHROPIC_API_KEY	Optional fallback. Paid Anthropic API
REQUEST_TIMEOUT	HTTP timeout in seconds (default: 30)
REQUEST_DELAY_MS	Delay between page requests in ms (default: 800)
MAX_CONCURRENT_REQUESTS	Parallel image download workers (default: 4)
LOG_LEVEL	DEBUG / INFO / WARNING / ERROR (default: INFO)
LLM Priority
The agent tries LLM providers in this order:

Groq (GROQ_API_KEY): free and fast (llama3-70b). Recommended.
Ollama (http://localhost:11434): local and free, requires ollama serve to be running.
Anthropic Claude (ANTHROPIC_API_KEY): paid fallback.
If none are available, visual analysis (images, colors, clusters) still runs fully. Only the textual synthesis sections (brand voice, audience, positioning) are skipped.

Output
outputs/brand_name/
├── images/                  # downloaded, filtered fashion images
├── image_metadata.json      # per-image record (URL, page context, cluster, phash)
├── text_corpus.json         # crawled page text + Instagram captions
└── brandname_brand_dna.pdf  # the Brand DNA report
Tests
pytest tests/ -v
Tests cover: config loading, deduplication (exact and distinct), color palette extraction, page type classification, domain checking, image URL extraction and a PDF generation smoke test.

Dependencies
Library	Purpose
aiohttp	Async HTTP crawling and image download
beautifulsoup4 / lxml	HTML parsing
Pillow	Image loading, resize, format conversion
imagehash	Perceptual hash deduplication
sentence-transformers (CLIP)	Fashion classification and visual embeddings
scikit-learn	KMeans clustering and color clustering
anthropic	Optional paid LLM provider (Anthropic Claude)
reportlab	PDF generation
instaloader	Instagram caption and image collection
structlog	Structured logging
pydantic	Config validation
click	CLI
Anti-bot, Rate Limiting and ToS
Request pacing: a configurable delay (REQUEST_DELAY_MS, default 800 ms) is inserted between every page fetch. Concurrent image downloads are capped at MAX_CONCURRENT_REQUESTS (default 4). Both values are tunable per run.

User-Agent: all requests use a realistic desktop browser User-Agent string to avoid trivial bot detection.

Instagram: the agent uses instaloader in public, unauthenticated mode.

Instagram enforces aggressive rate limits (HTTP 429) on unauthenticated scraping, typically after 10 to 15 profile requests within a short window.
When a 429 is received, the agent logs instagram_collection_failed with the reason and continues without Instagram data instead of crashing. The PDF is still produced from website data alone.
The log entry documents the failure explicitly: reason=429 Too Many Requests handle=<handle>.
Mitigation options (not implemented by default, documented for transparency): authenticated sessions via instaloader session files, rotating residential proxies, and exponential backoff with jitter. They are the natural next step for production use.
ToS: operators are responsible for making sure their use of this tool complies with the terms of service of any site they run it against. The agent is designed to be a polite crawler and does not attempt to circumvent explicit blocks.

Known Limitations
Single-page applications (React, Next.js) that render content client-side may yield fewer images. A Playwright fallback would address this.
Instagram collection is rate-sensitive in unauthenticated mode. A session cookie significantly improves reliability.
CLIP model weights (~600 MB) are downloaded on first run and cached locally.
PDF image quality is capped at the source resolution; very low-quality original images appear soft in the report.
The agent assumes a stable network. Transient failures are retried once; persistent failures are skipped with a structured log entry.

