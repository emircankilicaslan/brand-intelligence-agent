from __future__ import annotations

from pathlib import Path

import imagehash
from PIL import Image

from agent.logging_setup import get_logger
from agent.models import ImageRecord

logger = get_logger(__name__)

HASH_DISTANCE_THRESHOLD = 8


def deduplicate(records: list[ImageRecord]) -> list[ImageRecord]:
    seen_hashes: dict[str, str] = {}
    unique: list[ImageRecord] = []

    for record in records:
        try:
            with Image.open(record.local_path) as img:
                phash = str(imagehash.phash(img))
        except Exception as exc:
            logger.debug("phash_failed", path=record.local_path, error=str(exc))
            continue

        record.phash = phash
        is_duplicate = False

        for existing_hash in seen_hashes:
            try:
                distance = imagehash.hex_to_hash(phash) - imagehash.hex_to_hash(existing_hash)
                if distance <= HASH_DISTANCE_THRESHOLD:
                    is_duplicate = True
                    logger.debug("duplicate_found", path=record.local_path, distance=distance)
                    break
            except Exception:
                continue

        if not is_duplicate:
            seen_hashes[phash] = record.local_path
            unique.append(record)

    logger.info(
        "deduplication_complete",
        before=len(records),
        after=len(unique),
        removed=len(records) - len(unique),
    )
    return unique
