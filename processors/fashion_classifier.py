from __future__ import annotations

from pathlib import Path

from PIL import Image

from agent.logging_setup import get_logger
from agent.models import ImageRecord

logger = get_logger(__name__)

FASHION_LABELS = [
    "a photograph of clothing or fashion apparel",
    "a product shot of a garment",
    "a model wearing clothes",
    "a fashion lookbook photograph",
    "a photograph of shoes or footwear",
    "a photograph of a fashion accessory",
    "a store interior or retail space",
    "a landscape or nature photograph",
    "a website screenshot or UI element",
    "a logo or graphic design element",
    "a portrait photograph with no visible clothing focus",
    "a food or beverage photograph",
]

FASHION_POSITIVE_LABELS = {
    "a photograph of clothing or fashion apparel",
    "a product shot of a garment",
    "a model wearing clothes",
    "a fashion lookbook photograph",
    "a photograph of shoes or footwear",
    "a photograph of a fashion accessory",
}

GARMENT_CATEGORIES = [
    "tops and shirts",
    "trousers and pants",
    "dresses and skirts",
    "outerwear and coats",
    "knitwear and sweaters",
    "shoes and footwear",
    "accessories and bags",
    "swimwear and lingerie",
    "suits and tailoring",
    "activewear and sportswear",
]


class FashionClassifier:
    def __init__(self) -> None:
        self._model = None
        self._processor = None
        self._available = False
        self._load_model()

    def _load_model(self) -> None:
        try:
            from transformers import CLIPModel, CLIPProcessor
            import torch

            self._processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            self._model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self._model.eval()
            self._available = True
            logger.info("clip_model_loaded")
        except Exception as exc:
            logger.warning("clip_unavailable", error=str(exc), fallback="heuristic classifier")
            self._available = False

    def _clip_classify(self, image_path: str, labels: list[str]) -> dict[str, float]:
        import torch

        with Image.open(image_path) as img:
            img_rgb = img.convert("RGB")

        inputs = self._processor(text=labels, images=img_rgb, return_tensors="pt", padding=True)
        with torch.no_grad():
            outputs = self._model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1)[0].tolist()

        return {label: prob for label, prob in zip(labels, probs)}

    def _heuristic_classify(self, record: ImageRecord) -> tuple[bool, float]:
        fashion_keywords = {
            "product", "shop", "collection", "wear", "style", "look",
            "outfit", "garment", "apparel", "fashion", "dress", "coat",
            "jacket", "shirt", "pant", "trouser", "skirt", "shoe", "bag",
            "accessory", "model", "campaign", "lookbook",
        }
        combined = (record.alt_text + " " + record.surrounding_text + " " + record.source_page_url).lower()
        hits = sum(1 for kw in fashion_keywords if kw in combined)
        confidence = min(hits / 3.0, 1.0)
        return confidence >= 0.3, confidence

    def classify_batch(self, records: list[ImageRecord]) -> list[ImageRecord]:
        classified = []
        for record in records:
            try:
                if self._available:
                    scores = self._clip_classify(record.local_path, FASHION_LABELS)
                    positive_score = sum(scores.get(lbl, 0.0) for lbl in FASHION_POSITIVE_LABELS)
                    record.is_fashion = positive_score > 0.35
                    record.fashion_confidence = positive_score
                else:
                    record.is_fashion, record.fashion_confidence = self._heuristic_classify(record)
                classified.append(record)
            except Exception as exc:
                logger.debug("classify_failed", path=record.local_path, error=str(exc))
                record.is_fashion = True
                record.fashion_confidence = 0.5
                classified.append(record)

        fashion_count = sum(1 for r in classified if r.is_fashion)
        logger.info("classification_complete", total=len(classified), fashion=fashion_count)
        return [r for r in classified if r.is_fashion]

    def detect_garment_category(self, image_path: str) -> str:
        if not self._available:
            return "unknown"
        try:
            scores = self._clip_classify(image_path, GARMENT_CATEGORIES)
            return max(scores, key=scores.get)
        except Exception:
            return "unknown"
