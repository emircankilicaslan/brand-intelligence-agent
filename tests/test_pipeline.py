from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

def test_brand_config_from_dict():
    from agent.config import BrandConfig

    config = BrandConfig(brand_name="Test Brand", website_url="https://example.com")
    assert config.brand_name == "Test Brand"
    assert config.min_resolution == 512
    assert config.max_images == 150


def test_brand_config_from_file(tmp_path):
    import json
    from agent.config import BrandConfig

    cfg = {
        "brand_name": "Test Brand",
        "website_url": "https://example.com",
        "crawl_depth": 1,
        "max_images": 50,
        "min_resolution": 256,
        "output_dir": str(tmp_path),
    }
    p = tmp_path / "brand.json"
    p.write_text(json.dumps(cfg))
    loaded = BrandConfig.from_file(str(p))
    assert loaded.brand_name == "Test Brand"
    assert loaded.crawl_depth == 1
    assert loaded.max_images == 50


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------

def test_deduplicate_removes_exact_copies(tmp_path):
    from PIL import Image as PILImage
    from agent.models import ImageRecord
    from processors.deduplicator import deduplicate

    img = PILImage.new("RGB", (600, 600), color=(120, 60, 30))

    p1 = tmp_path / "img1.jpg"
    p2 = tmp_path / "img2.jpg"
    img.save(str(p1))
    img.save(str(p2))

    r1 = ImageRecord(url="http://a.com/1.jpg", local_path=str(p1), width=600, height=600, source_page_url="")
    r2 = ImageRecord(url="http://a.com/2.jpg", local_path=str(p2), width=600, height=600, source_page_url="")

    result = deduplicate([r1, r2])
    assert len(result) == 1


def test_deduplicate_keeps_different_images(tmp_path):
    import random
    from PIL import Image as PILImage
    from agent.models import ImageRecord
    from processors.deduplicator import deduplicate

    rng = random.Random(1)

    def make_noise_image(seed: int) -> PILImage.Image:
        rng2 = random.Random(seed)
        data = bytes(rng2.randint(0, 255) for _ in range(600 * 600 * 3))
        return PILImage.frombytes("RGB", (600, 600), data)

    img1 = make_noise_image(42)
    img2 = make_noise_image(9999)

    p1 = tmp_path / "img1.jpg"
    p2 = tmp_path / "img2.jpg"
    img1.save(str(p1))
    img2.save(str(p2))

    r1 = ImageRecord(url="http://a.com/1.jpg", local_path=str(p1), width=600, height=600, source_page_url="")
    r2 = ImageRecord(url="http://a.com/2.jpg", local_path=str(p2), width=600, height=600, source_page_url="")

    result = deduplicate([r1, r2])
    assert len(result) == 2


def test_deduplicate_handles_empty():
    from processors.deduplicator import deduplicate
    result = deduplicate([])
    assert result == []


# ---------------------------------------------------------------------------
# Color extractor tests
# ---------------------------------------------------------------------------

def test_extract_palette_returns_swatches(tmp_path):
    from PIL import Image as PILImage
    from processors.color_extractor import extract_palette

    colors_rgb = [(200, 30, 30), (30, 30, 200), (30, 200, 30), (200, 200, 30), (30, 200, 200)]
    paths = []
    for i, c in enumerate(colors_rgb):
        img = PILImage.new("RGB", (600, 600), color=c)
        p = tmp_path / f"color_{i}.jpg"
        img.save(str(p))
        paths.append(str(p))

    swatches = extract_palette(paths, n_colors=3)
    assert len(swatches) > 0
    assert all(hasattr(s, "hex") for s in swatches)
    assert all(0.0 <= s.frequency <= 1.0 for s in swatches)


def test_extract_palette_empty_input():
    from processors.color_extractor import extract_palette
    result = extract_palette([])
    assert result == []


# ---------------------------------------------------------------------------
# Website crawler tests
# ---------------------------------------------------------------------------

def test_classify_page_types():
    from collectors.website_crawler import _classify_page

    assert _classify_page("https://brand.com/about-us") == "about"
    assert _classify_page("https://brand.com/shop/dress") == "product"
    assert _classify_page("https://brand.com/journal/post-1") == "blog"
    assert _classify_page("https://brand.com/lookbook/ss24") == "lookbook"
    assert _classify_page("https://brand.com/faq") == "faq"
    assert _classify_page("https://brand.com/random-page") == "general"


def test_same_domain_check():
    from collectors.website_crawler import _is_same_domain

    assert _is_same_domain("https://www.brand.com", "https://brand.com/shop") is True
    assert _is_same_domain("https://brand.com", "https://otherbrand.com") is False
    assert _is_same_domain("https://brand.com", "https://cdn.brand.com/img.jpg") is False


def test_image_url_extraction():
    from collectors.website_crawler import WebsiteCrawler
    from agent.config import BrandConfig

    config = BrandConfig(brand_name="Test", website_url="https://example.com")
    crawler = WebsiteCrawler(config)

    html = """
    <html><body>
    <img src="/product/dress.jpg" alt="Red dress" />
    <img data-src="https://cdn.example.com/img2.jpg" alt="Coat" />
    <img src="logo.png" alt="logo" />
    </body></html>
    """
    metas = list(crawler.extract_image_urls(html, "https://example.com/shop"))
    urls = [m["url"] for m in metas]
    assert any("dress" in u for u in urls)
    assert any("img2" in u for u in urls)


# ---------------------------------------------------------------------------
# PDF generation smoke test
# ---------------------------------------------------------------------------

def test_pdf_generation_smoke(tmp_path):
    from agent.models import BrandDNA, ColorSwatch, VisualCluster
    from synthesizers.pdf_generator import generate_pdf

    dna = BrandDNA(
        brand_name="Smoke Test Brand",
        website_url="https://smoketest.com",
        run_id="test-001",
        brand_voice="Minimal and considered.",
        recurring_vocabulary=["effortless", "understated", "craft"],
        stated_values=["Sustainability", "Quality"],
        positioning_statement="Quiet luxury for the discerning few.",
        audience_demographics="Urban professionals, 28-45.",
        audience_psychographics="Values craft and longevity over trend.",
        silhouette_notes="Relaxed, unstructured silhouettes.",
        styling_cues="Tonal dressing with occasional texture contrast.",
        color_palette=[
            ColorSwatch(hex="#1A1A1A", rgb=(26, 26, 26), frequency=0.35, name="black"),
            ColorSwatch(hex="#F5F0EB", rgb=(245, 240, 235), frequency=0.28, name="off-white"),
        ],
        garment_categories={"coat": 12, "dress": 8, "trouser": 6},
        visual_clusters=[
            VisualCluster(
                cluster_id=0,
                label="Visual Group 1",
                description="Clean product shots on neutral backgrounds.",
                representative_images=[],
                size=25,
            )
        ],
        total_images_collected=80,
        total_images_after_filter=74,
        pages_crawled=22,
    )

    out = str(tmp_path / "smoke_test.pdf")
    result = generate_pdf(dna, out)
    assert Path(result).exists()
    assert Path(result).stat().st_size > 5000
