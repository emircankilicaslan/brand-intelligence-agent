from __future__ import annotations

import numpy as np
from PIL import Image

from agent.logging_setup import get_logger
from agent.models import ImageRecord, VisualCluster

logger = get_logger(__name__)


class VisualClusterer:
    def __init__(self) -> None:
        self._model = None
        self._processor = None
        self._available = False
        self._load()

    def _load(self) -> None:
        try:
            from transformers import CLIPModel, CLIPProcessor
            self._processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            self._model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self._model.eval()
            self._available = True
            logger.info("clip_loaded_for_clustering")
        except Exception as exc:
            logger.warning("clip_unavailable_for_clustering", error=str(exc))

    def _embed_images(self, paths: list[str]) -> np.ndarray:
        import torch

        embeddings = []
        batch_size = 16
        for i in range(0, len(paths), batch_size):
            batch_paths = paths[i : i + batch_size]
            images = []
            valid_idx = []
            for j, p in enumerate(batch_paths):
                try:
                    with Image.open(p) as img:
                        images.append(img.convert("RGB"))
                        valid_idx.append(j)
                except Exception:
                    pass

            if not images:
                continue

            inputs = self._processor(images=images, return_tensors="pt", padding=True)
            with torch.no_grad():
                feats = self._model.get_image_features(**inputs)
                feats = feats / feats.norm(dim=-1, keepdim=True)
            embeddings.extend(feats.cpu().numpy())

        return np.array(embeddings) if embeddings else np.zeros((0, 512))

    def _simple_cluster(self, records: list[ImageRecord], n_clusters: int) -> list[ImageRecord]:
        for i, record in enumerate(records):
            record.cluster_id = i % n_clusters
        return records

    def cluster(self, records: list[ImageRecord], n_clusters: int = 5) -> list[ImageRecord]:
        if not records:
            return records

        n_clusters = min(n_clusters, len(records))

        if not self._available:
            logger.info("using_simple_clustering")
            return self._simple_cluster(records, n_clusters)

        paths = [r.local_path for r in records]
        embeddings = self._embed_images(paths)

        if len(embeddings) < n_clusters:
            return self._simple_cluster(records, n_clusters)

        try:
            from sklearn.cluster import KMeans

            km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
            labels = km.fit_predict(embeddings)
            for record, label in zip(records, labels):
                record.cluster_id = int(label)
            logger.info("visual_clustering_done", n_clusters=n_clusters)
        except Exception as exc:
            logger.warning("clustering_failed", error=str(exc))
            return self._simple_cluster(records, n_clusters)

        return records

    def build_cluster_summaries(self, records: list[ImageRecord]) -> list[VisualCluster]:
        from collections import defaultdict

        groups: dict[int, list[ImageRecord]] = defaultdict(list)
        for r in records:
            if r.cluster_id >= 0:
                groups[r.cluster_id].append(r)

        clusters = []
        for cluster_id, members in sorted(groups.items()):
            representative_paths = [m.local_path for m in members[:4]]
            combined_text = " ".join(
                m.alt_text + " " + m.surrounding_text for m in members if m.alt_text or m.surrounding_text
            )[:400]
            clusters.append(
                VisualCluster(
                    cluster_id=cluster_id,
                    label=f"Visual Group {cluster_id + 1}",
                    description=combined_text or "No description available",
                    representative_images=representative_paths,
                    size=len(members),
                )
            )

        return clusters
