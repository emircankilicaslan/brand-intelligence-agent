from __future__ import annotations

import asyncio
import re
import time
from collections import deque
from typing import Generator
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from agent.config import BrandConfig, settings
from agent.logging_setup import get_logger
from agent.models import PageContent

logger = get_logger(__name__)

PAGE_TYPE_PATTERNS = {
    "product": [r"/product", r"/shop", r"/item", r"/p/", r"/collections/", r"/catalogue"],
    "about": [r"/about", r"/story", r"/our-story", r"/brand", r"/who-we-are"],
    "blog": [r"/blog", r"/journal", r"/editorial", r"/notes", r"/stories"],
    "lookbook": [r"/lookbook", r"/campaign", r"/collection", r"/season"],
    "press": [r"/press", r"/media", r"/news"],
    "faq": [r"/faq", r"/help", r"/customer-service"],
}


def _classify_page(url: str) -> str:
    path = urlparse(url).path.lower()
    for page_type, patterns in PAGE_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, path):
                return page_type
    return "general"


def _is_same_domain(base: str, url: str) -> bool:
    base_host = urlparse(base).netloc.replace("www.", "")
    url_host = urlparse(url).netloc.replace("www.", "")
    return base_host == url_host


def _extract_links(soup: BeautifulSoup, base_url: str, origin: str) -> list[str]:
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.scheme in ("http", "https") and _is_same_domain(origin, full):
            links.append(full.split("#")[0].split("?")[0])
    return list(set(links))


def _extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s{2,}", " ", text).strip()


class WebsiteCrawler:
    def __init__(self, config: BrandConfig) -> None:
        self.config = config
        self.origin = config.website_url.rstrip("/")
        self._visited: set[str] = set()
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
            headers = {"User-Agent": settings.user_agent, "Accept-Language": "en-US,en;q=0.9"}
            self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self._session

    async def _fetch(self, url: str) -> str | None:
        session = await self._get_session()
        try:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status == 200 and "text/html" in resp.content_type:
                    return await resp.text(errors="replace")
                logger.debug("skipped_url", url=url, status=resp.status)
        except Exception as exc:
            logger.warning("fetch_failed", url=url, error=str(exc))
        return None

    async def crawl(self) -> list[PageContent]:
        pages: list[PageContent] = []
        queue: deque[tuple[str, int]] = deque([(self.origin, 0)])
        self._visited.add(self.origin)

        logger.info("crawl_started", origin=self.origin, max_depth=self.config.crawl_depth)

        while queue:
            url, depth = queue.popleft()
            html = await self._fetch(url)
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag["content"].strip()

            body_text = _extract_text(soup)
            page_type = _classify_page(url)

            pages.append(
                PageContent(
                    url=url,
                    title=title,
                    body_text=body_text,
                    meta_description=meta_desc,
                    page_type=page_type,
                )
            )
            logger.info("page_crawled", url=url, depth=depth, page_type=page_type, text_len=len(body_text))

            if depth < self.config.crawl_depth:
                child_links = _extract_links(soup, url, self.origin)
                for link in child_links:
                    if link not in self._visited:
                        self._visited.add(link)
                        queue.append((link, depth + 1))

            await asyncio.sleep(settings.request_delay_ms / 1000)

        if self._session and not self._session.closed:
            await self._session.close()

        logger.info("crawl_finished", pages_collected=len(pages))
        return pages

    def extract_image_urls(self, html: str, page_url: str) -> Generator[dict, None, None]:
        soup = BeautifulSoup(html, "lxml")

        def clean(url: str) -> str:
            url = url.strip()
            if url.startswith("//"):
                url = "https:" + url
            return urljoin(page_url, url)

        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("data-lazy-src") or img.get("src", "")
            if src:
                surrounding = ""
                parent = img.parent
                if parent:
                    surrounding = parent.get_text(separator=" ", strip=True)[:200]
                yield {
                    "url": clean(src),
                    "alt": img.get("alt", ""),
                    "surrounding_text": surrounding,
                    "source_page": page_url,
                }

        for source in soup.find_all("source"):
            srcset = source.get("srcset", "")
            for part in srcset.split(","):
                part = part.strip().split()[0]
                if part:
                    yield {"url": clean(part), "alt": "", "surrounding_text": "", "source_page": page_url}
