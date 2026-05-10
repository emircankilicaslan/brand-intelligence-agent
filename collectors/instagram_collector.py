from __future__ import annotations

import time
from agent.config import BrandConfig
from agent.logging_setup import get_logger

logger = get_logger(__name__)


class InstagramCollector:
    def __init__(self, config: BrandConfig) -> None:
        self.config = config
        self.handle = (config.social_handles.instagram or "").lstrip("@")

    def _get_loader(self):
        import instaloader
        L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            quiet=True,
            request_timeout=10,
        )
        L.context.sleep = False
        L.context.max_connection_attempts = 1
        return L

    def collect_captions(self, max_posts: int = 50) -> list[str]:
        if not self.handle:
            logger.info("instagram_skipped", reason="no handle configured")
            return []
        try:
            import instaloader
            L = self._get_loader()
            profile = instaloader.Profile.from_username(L.context, self.handle)
            captions: list[str] = []
            for post in profile.get_posts():
                if len(captions) >= max_posts:
                    break
                if post.caption:
                    captions.append(post.caption)
                time.sleep(0.5)
            logger.info("instagram_captions_collected", handle=self.handle, count=len(captions))
            return captions
        except Exception as exc:
            logger.warning(
                "instagram_collection_failed",
                handle=self.handle,
                error=str(exc)[:120],
                note="Continuing without Instagram data — rate limited or blocked",
            )
            return []

    def collect_image_urls(self, max_posts: int = 40) -> list[dict]:
        if not self.handle:
            return []
        try:
            import instaloader
            L = self._get_loader()
            profile = instaloader.Profile.from_username(L.context, self.handle)
            metas: list[dict] = []
            for post in profile.get_posts():
                if len(metas) >= max_posts:
                    break
                try:
                    metas.append({
                        "url": post.url,
                        "alt": post.caption[:120] if post.caption else "",
                        "surrounding_text": post.caption[:200] if post.caption else "",
                        "source_page": f"https://www.instagram.com/{self.handle}/",
                    })
                except Exception:
                    pass
                time.sleep(0.5)
            logger.info("instagram_images_found", handle=self.handle, count=len(metas))
            return metas
        except Exception as exc:
            logger.warning("instagram_images_failed", handle=self.handle, error=str(exc)[:120])
            return []
