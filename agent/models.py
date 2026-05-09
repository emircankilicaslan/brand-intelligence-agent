from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ImageRecord:
    url: str
    local_path: str
    width: int
    height: int
    source_page_url: str
    alt_text: str = ""
    surrounding_text: str = ""
    product_name: str = ""
    page_context: str = ""
    capture_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    phash: str = ""
    is_fashion: bool = False
    fashion_confidence: float = 0.0
    cluster_id: int = -1


@dataclass
class PageContent:
    url: str
    title: str
    body_text: str
    meta_description: str = ""
    page_type: str = "unknown"
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class BrandTextCorpus:
    pages: list[PageContent] = field(default_factory=list)
    instagram_captions: list[str] = field(default_factory=list)
    product_names: list[str] = field(default_factory=list)
    raw_text_blob: str = ""


@dataclass
class ColorSwatch:
    hex: str
    rgb: tuple[int, int, int]
    frequency: float
    name: str = ""


@dataclass
class VisualCluster:
    cluster_id: int
    label: str
    description: str
    representative_images: list[str]
    size: int


@dataclass
class BrandDNA:
    brand_name: str
    website_url: str
    run_id: str
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    color_palette: list[ColorSwatch] = field(default_factory=list)
    garment_categories: dict[str, float] = field(default_factory=dict)
    silhouette_notes: str = ""
    styling_cues: str = ""

    brand_voice: str = ""
    recurring_vocabulary: list[str] = field(default_factory=list)
    stated_values: list[str] = field(default_factory=list)
    positioning_statement: str = ""

    audience_demographics: str = ""
    audience_psychographics: str = ""

    visual_clusters: list[VisualCluster] = field(default_factory=list)

    total_images_collected: int = 0
    total_images_after_filter: int = 0
    pages_crawled: int = 0
    instagram_posts_scraped: int = 0
