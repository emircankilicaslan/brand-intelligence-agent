# Brand Intelligence Agent

![CI](https://github.com/emircankilicaslan/brand-intelligence-agent/actions/workflows/ci.yml/badge.svg)

> **English summary:** Given only a brand name, a URL and an optional Instagram handle, this Python agent crawls the brand's website, filters and clusters fashion images (CLIP + KMeans), extracts a color palette, synthesizes brand voice and audience with an LLM (Groq → Ollama → Anthropic fallback) and renders a PDF "Brand DNA" dossier. Config-driven, Dockerized, unit-tested, CI on GitHub Actions.

Yalnızca bir marka adı, bir URL ve isteğe bağlı bir Instagram kullanıcı adı verilen herhangi bir moda markası için yapılandırılmış bir **Marka DNA'sı dosyasını** (renk paleti, görsel kümeler, marka sesi ve hedef kitle sinyalleri) otonom olarak üretir.

---

## Nasıl çalışır

1. **Topla:** Marka web sitesini (ayarlanabilir derinlikte) tarar; mümkünse herkese açık Instagram açıklamalarını ve görsellerini de alır.
2. **Filtrele:** Yalnızca minimum çözünürlüğü karşılayan moda görsellerini tutar, algısal karma (perceptual hash) ile kopyaları ayıklar.
3. **Görselleri analiz et:** CLIP gömmeleri, KMeans ile görsel kümeler ve baskın renk paleti.
4. **Metni sentezle:** Marka sesi, hedef kitle ve konumlandırma bir LLM sağlayıcısıyla yazılır.
5. **Raporla:** Her şey PDF biçiminde bir Marka DNA raporuna dönüştürülür.

---

## Hızlı başlangıç

### Gereksinimler

- Python 3.11+
- Metin bölümleri için bir LLM sağlayıcısı ([LLM önceliği](#llm-önceliği) bölümüne bakın). Kredi kartı gerektirmeyen ücretsiz bir [Groq API anahtarı](https://console.groq.com) önerilir.

### Kurulum

```bash
git clone https://github.com/emircankilicaslan/brand-intelligence-agent.git
cd brand-intelligence-agent
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env dosyasını düzenleyip GROQ_API_KEY değerini girin
```

### Çalıştırma

```bash
python main.py configs/acne_studios.json
```

Rapor `outputs/acne_studios/acne_studios_brand_dna.pdf` dosyasına yazılır.

---

## Docker

```bash
docker build -t brand-agent .
docker run --rm \
  -v $(pwd)/configs:/app/configs \
  -v $(pwd)/outputs:/app/outputs \
  -e GROQ_API_KEY=anahtariniz \
  brand-agent configs/acne_studios.json
```

---

## Yapılandırma

Her marka bir JSON dosyasıdır; kod değişikliği gerekmez.

```json
{
  "brand_name": "Acne Studios",
  "website_url": "https://www.acnestudios.com",
  "social_handles": {
    "instagram": "acnestudios"
  },
  "crawl_depth": 2,
  "max_images": 150,
  "min_resolution": 512,
  "output_dir": "outputs/acne_studios"
}
```

| Alan | Varsayılan | Açıklama |
|---|---|---|
| `brand_name` | zorunlu | Raporda görünen ad |
| `website_url` | zorunlu | Taramanın başladığı ana sayfa |
| `social_handles.instagram` | `null` | Instagram kullanıcı adı (@ olmadan) |
| `crawl_depth` | 2 | Ana sayfadan kaç bağlantı adımı takip edileceği |
| `max_images` | 150 | Filtreleme sonrası tutulacak moda görseli üst sınırı |
| `min_resolution` | 512 | Kısa kenarda minimum piksel |
| `output_dir` | `outputs` | Görsellerin, üst verinin ve PDF'in yazılacağı yer |

Ortam değişkenleri (`.env`):

| Değişken | Açıklama |
|---|---|
| `GROQ_API_KEY` | **Önerilir.** Marka sesi sentezi için ücretsiz LLM. console.groq.com adresinden alınır |
| `ANTHROPIC_API_KEY` | İsteğe bağlı yedek. Ücretli Anthropic API |
| `REQUEST_TIMEOUT` | HTTP zaman aşımı, saniye (varsayılan: 30) |
| `REQUEST_DELAY_MS` | Sayfa istekleri arası bekleme, ms (varsayılan: 800) |
| `MAX_CONCURRENT_REQUESTS` | Paralel görsel indirme işçisi sayısı (varsayılan: 4) |
| `LOG_LEVEL` | DEBUG / INFO / WARNING / ERROR (varsayılan: INFO) |

---

## LLM önceliği

Ajan LLM sağlayıcılarını şu sırayla dener:

1. **Groq** (`GROQ_API_KEY`): ücretsiz ve hızlı (llama3-70b). Önerilir.
2. **Ollama** (`http://localhost:11434`): yerel ve ücretsiz; `ollama serve` çalışıyor olmalıdır.
3. **Anthropic Claude** (`ANTHROPIC_API_KEY`): ücretli yedek.

Hiçbiri yoksa görsel analiz (görseller, renkler, kümeler) yine tam olarak çalışır; yalnızca metin sentezi bölümleri (marka sesi, hedef kitle, konumlandırma) atlanır.

---

## Çıktı

```
outputs/marka_adi/
├── images/                  # indirilen, filtrelenmiş moda görselleri
├── image_metadata.json      # görsel başına kayıt (URL, sayfa bağlamı, küme, phash)
├── text_corpus.json         # taranan sayfa metni + Instagram açıklamaları
└── markaadi_brand_dna.pdf   # Marka DNA raporu
```

---

## Testler

```bash
pip install -r requirements-test.txt   # ağır CLIP/torch bağımlılıkları olmadan çalışır
python -m pytest tests -v
```

Testler şunları kapsar: yapılandırma yükleme, kopya ayıklama (birebir ve farklı), renk paleti çıkarımı, sayfa türü sınıflandırma, alan adı denetimi, görsel URL çıkarımı ve PDF üretimi duman testi.

---

## Bağımlılıklar

| Kütüphane | Amaç |
|---|---|
| aiohttp | Asenkron HTTP tarama ve görsel indirme |
| beautifulsoup4 / lxml | HTML ayrıştırma |
| Pillow | Görsel yükleme, yeniden boyutlandırma, biçim dönüşümü |
| imagehash | Algısal karma ile kopya ayıklama |
| sentence-transformers (CLIP) | Moda sınıflandırma ve görsel gömmeler |
| scikit-learn | KMeans kümeleme ve renk kümeleme |
| anthropic | İsteğe bağlı ücretli LLM sağlayıcısı (Anthropic Claude) |
| reportlab | PDF üretimi |
| instaloader | Instagram açıklama ve görsel toplama |
| structlog | Yapılandırılmış günlükleme |
| pydantic | Yapılandırma doğrulama |
| click | Komut satırı arayüzü |

---

## Bot engeli, hız sınırı ve kullanım koşulları

**İstek aralığı:** Her sayfa isteği arasına ayarlanabilir bir bekleme (`REQUEST_DELAY_MS`, varsayılan 800 ms) konur. Eşzamanlı görsel indirmeleri `MAX_CONCURRENT_REQUESTS` (varsayılan 4) ile sınırlıdır. Her iki değer de çalıştırma başına ayarlanabilir.

**User-Agent:** Basit bot tespitine takılmamak için tüm istekler gerçekçi bir masaüstü tarayıcı User-Agent'ı kullanır.

**Instagram:** Ajan `instaloader`'ı herkese açık, oturumsuz modda kullanır.

- Instagram, oturumsuz taramada agresif hız sınırı (HTTP 429) uygular; genellikle kısa sürede 10–15 profil isteğinden sonra devreye girer.
- 429 alındığında ajan nedenini belirterek `instagram_collection_failed` kaydı düşer ve çökmek yerine **Instagram verisi olmadan devam eder**; PDF yalnızca web sitesi verisiyle yine üretilir.
- Günlük kaydı hatayı açıkça belgeler: `reason=429 Too Many Requests handle=<kullanıcı>`.
- Hafifletme seçenekleri (varsayılan olarak uygulanmamıştır, şeffaflık için belirtilmiştir): `instaloader` oturum dosyalarıyla kimlik doğrulamalı oturum, dönen konut proxy'leri ve jitter'lı üstel geri çekilme. Üretim kullanımı için doğal sonraki adımlardır.

**Kullanım koşulları:** Aracın çalıştırıldığı sitelerin kullanım koşullarına uyulması işletenin sorumluluğundadır. Ajan nazik bir tarayıcı olarak tasarlanmıştır ve açık engelleri aşmaya çalışmaz.

---

## Bilinen sınırlamalar

- İçeriği istemci tarafında oluşturan tek sayfa uygulamalar (React, Next.js) daha az görsel verebilir. Bir Playwright yedeği bunu çözer.
- Instagram toplama, oturumsuz modda hız sınırına duyarlıdır. Bir oturum çerezi güvenilirliği belirgin biçimde artırır.
- CLIP model ağırlıkları (~600 MB) ilk çalıştırmada indirilir ve yerelde önbelleğe alınır.
- PDF görsel kalitesi kaynak çözünürlükle sınırlıdır; çok düşük kaliteli özgün görseller raporda yumuşak görünür.
- Ajan kararlı bir ağ varsayar. Geçici hatalar bir kez yeniden denenir; kalıcı hatalar yapılandırılmış bir günlük kaydıyla atlanır.