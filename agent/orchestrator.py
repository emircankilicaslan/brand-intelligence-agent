from __future__ import annotations

import asyncio
import json
import uuid
from collections import Counter
from pathlib import Path

import structlog

from agent.config import BrandConfig, settings
from agent.logging_setup import configure_logging, get_logger
from agent.models import BrandDNA, BrandTextCorpus, ImageRecord
from collectors.image_downloader import ImageDownloader
from collectors.instagram_collector import InstagramCollector
from collectors.website_crawler import WebsiteCrawler
from processors.color_extractor import extract_palette
from processors.deduplicator import deduplicate
from processors.fashion_classifier import FashionClassifier
from processors.visual_clusterer import VisualClusterer
from synthesizers.pdf_generator import generate_pdf
from synthesizers.text_analyzer import (
    analyze_brand_voice,
    describe_visual_clusters,
    synthesize_visual_identity,
)

logger = get_logger(__name__)


class BrandIntelligenceAgent:
    def __init__(self, config: BrandConfig) -> None:
        self.config = config
        self.run_id = str(uuid.uuid4())[:8]
        self.output_dir = Path(config.output_dir)
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

        structlog.contextvars.bind_contextvars(run_id=self.run_id, brand=config.brand_name)

    async def _collect_website_images(self) -> tuple[list[dict], BrandTextCorpus]:
        crawler = WebsiteCrawler(self.config)
        pages = await crawler.crawl()
        corpus = BrandTextCorpus(pages=pages)

        image_metas: list[dict] = []
        seen_urls: set[str] = set()

        for page in pages:
            try:
                import aiohttp
                timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
                headers = {"User-Agent": settings.user_agent}
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as sess:
                    async with sess.get(page.url) as resp:
                        if resp.status == 200:
                            html = await resp.text(errors="replace")
                            for meta in crawler.extract_image_urls(html, page.url):
                                if meta["url"] not in seen_urls:
                                    seen_urls.add(meta["url"])
                                    image_metas.append(meta)
            except Exception as exc:
                logger.debug("image_url_extract_failed", url=page.url, error=str(exc))

            await asyncio.sleep(settings.request_delay_ms / 1000)

        corpus.product_names = list(
            set(
                p.title for p in pages
                if p.page_type == "product" and p.title
            )
        )

        logger.info("website_images_found", count=len(image_metas), pages=len(pages))
        return image_metas, corpus

    def _collect_instagram(self, corpus: BrandTextCorpus) -> list[dict]:
        collector = InstagramCollector(self.config)
        captions = collector.collect_captions(max_posts=50)
        corpus.instagram_captions = captions
        image_metas = collector.collect_image_urls(max_posts=40)
        return image_metas

    async def _download_and_filter(self, image_metas: list[dict]) -> list[ImageRecord]:
        downloader = ImageDownloader(self.config, self.images_dir)
        records = await downloader.download_batch(image_metas)
        logger.info("downloaded", count=len(records))

        records = deduplicate(records)

        classifier = FashionClassifier()
        records = classifier.classify_batch(records)

        if len(records) > self.config.max_images:
            records = records[: self.config.max_images]

        logger.info("filtered_images", final_count=len(records))
        return records

    def _build_dna(
        self,
        records: list[ImageRecord],
        corpus: BrandTextCorpus,
        clusters,
    ) -> BrandDNA:
        dna = BrandDNA(
            brand_name=self.config.brand_name,
            website_url=self.config.website_url,
            run_id=self.run_id,
            total_images_collected=len(records),
            total_images_after_filter=len(records),
            pages_crawled=len(corpus.pages),
            instagram_posts_scraped=len(corpus.instagram_captions),
        )

        dna.color_palette = extract_palette([r.local_path for r in records])

        garment_raw: Counter = Counter()
        for r in records:
            if r.surrounding_text or r.alt_text:
                combined = (r.alt_text + " " + r.surrounding_text).lower()
                for cat in [
                    "dress", "skirt", "trouser", "pant", "jacket", "coat",
                    "shirt", "top", "knitwear", "sweater", "shoe", "bag", "accessory",
                ]:
                    if cat in combined:
                        garment_raw[cat] += 1
        dna.garment_categories = dict(garment_raw.most_common(10))

        voice_data = analyze_brand_voice(corpus, self.config.brand_name)
        dna.brand_voice = voice_data.get("brand_voice", "")
        dna.recurring_vocabulary = voice_data.get("recurring_vocabulary", [])
        dna.stated_values = voice_data.get("stated_values", [])
        dna.positioning_statement = voice_data.get("positioning_statement", "")
        dna.audience_demographics = voice_data.get("audience_demographics", "")
        dna.audience_psychographics = voice_data.get("audience_psychographics", "")

        visual_data = synthesize_visual_identity(
            dna.garment_categories,
            dna.color_palette,
            self.config.brand_name,
            [r.alt_text for r in records],
        )
        dna.silhouette_notes = visual_data.get("silhouette_notes", "")
        dna.styling_cues = visual_data.get("styling_cues", "")

        described_clusters = describe_visual_clusters(clusters, self.config.brand_name, dna.color_palette)
        dna.visual_clusters = described_clusters

        return dna

    def _save_metadata(self, records: list[ImageRecord], corpus: BrandTextCorpus) -> None:
        meta_path = self.output_dir / "image_metadata.json"
        data = []
        for r in records:
            data.append(
                {
                    "url": r.url,
                    "local_path": r.local_path,
                    "width": r.width,
                    "height": r.height,
                    "source_page_url": r.source_page_url,
                    "alt_text": r.alt_text,
                    "surrounding_text": r.surrounding_text,
                    "product_name": r.product_name,
                    "capture_timestamp": r.capture_timestamp,
                    "phash": r.phash,
                    "cluster_id": r.cluster_id,
                    "fashion_confidence": r.fashion_confidence,
                }
            )
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        text_path = self.output_dir / "text_corpus.json"
        corpus_data = {
            "pages": [
                {
                    "url": p.url,
                    "title": p.title,
                    "page_type": p.page_type,
                    "body_text": p.body_text[:2000],
                    "meta_description": p.meta_description,
                }
                for p in corpus.pages
            ],
            "instagram_captions": corpus.instagram_captions,
            "product_names": corpus.product_names,
        }
        with open(text_path, "w", encoding="utf-8") as f:
            json.dump(corpus_data, f, indent=2, ensure_ascii=False)

        logger.info("metadata_saved", image_meta=str(meta_path), text_corpus=str(text_path))

    async def run(self) -> str:
        logger.info("agent_started", brand=self.config.brand_name, run_id=self.run_id)

        try:
            image_metas, corpus = await self._collect_website_images()
        except Exception as exc:
            logger.error("website_collection_failed", error=str(exc))
            image_metas, corpus = [], BrandTextCorpus()

        try:
            ig_metas = self._collect_instagram(corpus)
            image_metas.extend(ig_metas)
        except Exception as exc:
            logger.warning("instagram_failed_gracefully", error=str(exc))

        if not image_metas:
            logger.error("no_images_found", brand=self.config.brand_name)
            raise RuntimeError(f"No images collected for {self.config.brand_name}. Check the URL and network access.")

        records = await self._download_and_filter(image_metas)

        if not records:
            logger.error("no_fashion_images_after_filter", brand=self.config.brand_name)
            raise RuntimeError("All images were filtered out. Check resolution and fashion classifier thresholds.")

        n_clusters = min(5, max(3, len(records) // 20))
        clusterer = VisualClusterer()
        records = clusterer.cluster(records, n_clusters=n_clusters)
        clusters = clusterer.build_cluster_summaries(records)

        self._save_metadata(records, corpus)

        dna = self._build_dna(records, corpus, clusters)

        brand_slug = self.config.brand_name.lower().replace(" ", "_")
        pdf_path = str(self.output_dir / f"{brand_slug}_brand_dna.pdf")
        generate_pdf(dna, pdf_path)

        logger.info(
            "agent_finished",
            brand=self.config.brand_name,
            pdf=pdf_path,
            images=len(records),
            pages=len(corpus.pages),
        )
        return pdf_path


def run_agent(config_path: str) -> str:
    configure_logging(settings.log_level)
    config = BrandConfig.from_file(config_path)
    agent = BrandIntelligenceAgent(config)
    return asyncio.run(agent.run())
