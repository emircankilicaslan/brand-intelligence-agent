from __future__ import annotations

import asyncio
import hashlib
import os
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import aiofiles
from PIL import Image

from agent.config import BrandConfig, settings
from agent.logging_setup import get_logger
from agent.models import ImageRecord

logger = get_logger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SKIP_PATTERNS = re.compile(
    r"(logo|icon|avatar|favicon|sprite|placeholder|banner-bg|bg-\d|pixel|tracking|badge|seal)",
    re.IGNORECASE,
)


def _url_to_filename(url: str) -> str:
    digest = hashlib.md5(url.encode()).hexdigest()[:12]
    ext = Path(urlparse(url).path).suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        ext = ".jpg"
    return f"{digest}{ext}"


def _passes_heuristic_filter(url: str, alt: str) -> bool:
    if SKIP_PATTERNS.search(url) or SKIP_PATTERNS.search(alt):
        return False
    ext = Path(urlparse(url).path).suffix.lower()
    if ext and ext not in IMAGE_EXTENSIONS:
        return False
    return True


class ImageDownloader:
    def __init__(self, config: BrandConfig, output_dir: Path) -> None:
        self.config = config
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_requests)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
            headers = {"User-Agent": settings.user_agent}
            self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self._session

    async def _download_one(self, image_meta: dict) -> ImageRecord | None:
        url = image_meta["url"]
        if not _passes_heuristic_filter(url, image_meta.get("alt", "")):
            return None

        filename = _url_to_filename(url)
        local_path = self.output_dir / filename

        if local_path.exists():
            try:
                with Image.open(local_path) as img:
                    w, h = img.size
                if min(w, h) < self.config.min_resolution:
                    return None
                return ImageRecord(
                    url=url,
                    local_path=str(local_path),
                    width=w,
                    height=h,
                    source_page_url=image_meta.get("source_page", ""),
                    alt_text=image_meta.get("alt", ""),
                    surrounding_text=image_meta.get("surrounding_text", ""),
                )
            except Exception:
                pass

        async with self._semaphore:
            session = await self._get_session()
            try:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        return None
                    content = await resp.read()
            except Exception as exc:
                logger.debug("image_download_failed", url=url, error=str(exc))
                return None

        try:
            with Image.open(BytesIO(content)) as img:
                img.verify()
            with Image.open(BytesIO(content)) as img:
                w, h = img.size
                if min(w, h) < self.config.min_resolution:
                    logger.debug("image_too_small", url=url, width=w, height=h)
                    return None
                img_rgb = img.convert("RGB")
                img_rgb.save(str(local_path), quality=90)
        except Exception as exc:
            logger.debug("image_invalid", url=url, error=str(exc))
            return None

        record = ImageRecord(
            url=url,
            local_path=str(local_path),
            width=w,
            height=h,
            source_page_url=image_meta.get("source_page", ""),
            alt_text=image_meta.get("alt", ""),
            surrounding_text=image_meta.get("surrounding_text", ""),
        )
        logger.debug("image_saved", url=url, size=f"{w}x{h}")
        return record

    async def download_batch(self, image_metas: list[dict]) -> list[ImageRecord]:
        tasks = [self._download_one(meta) for meta in image_metas]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        records = []
        for r in results:
            if isinstance(r, ImageRecord):
                records.append(r)
        logger.info("batch_downloaded", total=len(image_metas), saved=len(records))

        if self._session and not self._session.closed:
            await self._session.close()

        return records
