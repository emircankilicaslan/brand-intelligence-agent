"""Örnek Marka DNA raporu üretir (kurgusal marka, yer tutucu görseller).

Gerçek bir marka taranmadan, rapor biçimini göstermek için kullanılır.
Çıktı: docs/ornek/ornek_marka_brand_dna.pdf

Kullanım (depo kökünden):
    python scripts/ornek_rapor_uret.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.models import BrandDNA, ColorSwatch, VisualCluster  # noqa: E402
from synthesizers.pdf_generator import generate_pdf  # noqa: E402

OUT_DIR = ROOT / "docs" / "ornek"

# Kurgusal markanın paleti
PALETTE = [
    ("#1F1D1B", "kömür siyahı", 0.31),
    ("#EAE3D8", "kırık beyaz", 0.27),
    ("#8C7B6B", "toprak", 0.16),
    ("#4A5A4C", "zeytin", 0.12),
    ("#B9A58C", "kum", 0.09),
    ("#C26A4A", "kiremit", 0.05),
]


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _placeholder(path: Path, base: str, accent: str, size=(640, 800)) -> None:
    """Gerçek fotoğraf yerine paletten türetilmiş degrade bir yer tutucu çizer."""
    w, h = size
    c1, c2 = _hex_to_rgb(base), _hex_to_rgb(accent)
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        row = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
        for x in range(w):
            px[x, y] = row
    d = ImageDraw.Draw(img)
    d.rectangle([w * 0.3, h * 0.18, w * 0.7, h * 0.82], outline=(255, 255, 255), width=3)
    d.text((w * 0.34, h * 0.48), "ÖRNEK GÖRSEL", fill=(255, 255, 255))
    img.save(path, "JPEG", quality=88)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img_dir = OUT_DIR / "_gecici"
    img_dir.mkdir(exist_ok=True)

    combos = [
        (PALETTE[0][0], PALETTE[2][0]), (PALETTE[1][0], PALETTE[4][0]),
        (PALETTE[3][0], PALETTE[0][0]), (PALETTE[2][0], PALETTE[1][0]),
        (PALETTE[5][0], PALETTE[1][0]), (PALETTE[4][0], PALETTE[3][0]),
    ]
    images = []
    for i, (a, b) in enumerate(combos):
        p = img_dir / f"gorsel_{i}.jpg"
        _placeholder(p, a, b)
        images.append(str(p))

    dna = BrandDNA(
        brand_name="Örnek Marka (kurgusal)",
        website_url="https://ornek-marka.example",
        run_id="ornek-001",
        brand_voice=(
            "Sakin, sade ve özenli bir ton. Cümleler kısa; vurgu abartıdan çok "
            "malzemeye ve işçiliğe yapılıyor. Kampanya dili yerine ürün anlatımı öne çıkıyor."
        ),
        recurring_vocabulary=["zamansız", "işçilik", "doğal lifler", "rahat kesim", "mevsimsiz"],
        stated_values=["Sürdürülebilirlik", "Uzun ömürlü ürün", "Şeffaf üretim"],
        positioning_statement="Trend peşinde koşmayan, uzun yıllar giyilecek parçalar arayanlar için sessiz lüks.",
        audience_demographics="Şehirde yaşayan, 28-45 yaş arası, orta-üst gelirli profesyoneller.",
        audience_psychographics="Hızlı modadan uzak durur; kalite, işçilik ve parçanın ömrünü önemser.",
        silhouette_notes="Rahat, yapısız ve hafif oversize siluetler; omuzda düşük çizgi.",
        styling_cues="Tonal kombinler, yüzey dokusu farkıyla kurulan katmanlar, minimal aksesuar.",
        color_palette=[
            ColorSwatch(hex=h, rgb=_hex_to_rgb(h), frequency=f, name=n) for h, n, f in PALETTE
        ],
        garment_categories={"palto": 14, "elbise": 9, "pantolon": 7, "kazak": 6},
        visual_clusters=[
            VisualCluster(
                cluster_id=0, label="Görsel Grup 1",
                description="Nötr arka planda temiz ürün çekimleri.",
                representative_images=images[:3], size=31,
            ),
            VisualCluster(
                cluster_id=1, label="Görsel Grup 2",
                description="Doğal ışıkta, sokak ve iç mekân yaşam tarzı kareleri.",
                representative_images=images[3:], size=22,
            ),
        ],
        total_images_collected=96,
        total_images_after_filter=53,
        pages_crawled=24,
    )

    out = generate_pdf(dna, str(OUT_DIR / "ornek_marka_brand_dna.pdf"))
    print("PDF:", out)


if __name__ == "__main__":
    main()
