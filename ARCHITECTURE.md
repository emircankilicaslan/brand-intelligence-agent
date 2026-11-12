# Mimari Doküman — Brand Intelligence Agent

> **English summary:** Pipeline architecture of the Brand Intelligence Agent: async crawler → image download → pHash dedup → CLIP fashion classification and clustering → color extraction → LLM text synthesis (Groq → Ollama → Anthropic cascade) → PDF report. Every stage fails gracefully so partial output is always produced. Design decisions, trade-offs and a scaling plan are listed below.

## Sistem diyagramı

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI (main.py)                        │
│                click tabanlı giriş noktası                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               Orkestratör (agent/orchestrator.py)           │
│   Tüm hattı yönetir; hata sınırlarını elinde tutar          │
└──┬──────────────┬──────────────┬───────────────┬────────────┘
   │              │              │               │
   ▼              ▼              ▼               ▼
WebsiteCrawler  ImageDownloader InstagramColl.  TextAnalyzer
(async BFS)     (async toplu)   (instaloader)   (Groq/Ollama/Claude)
   │              │
   ▼              ▼
PageContent[]  diskte ham görseller
   │              │
   │          Deduplicator (pHash, Hamming ≤ 8)
   │              │
   │          FashionClassifier (CLIP sıfır-örnek / sezgisel yedek)
   │              │
   │          VisualClusterer (CLIP gömmeleri + KMeans)
   │              │
   └──────────────┼─────────────────┐
                  ▼                 ▼
            ColorExtractor     TextAnalyzer (LLM)
                  │                 │
                  └────────┬────────┘
                           ▼
                     BrandDNA veri sınıfı
                           │
                           ▼
                     PDFGenerator (reportlab)
                           │
                           ▼
                    {marka}_brand_dna.pdf
```

## Temel tasarım kararları

### 1. Siteden bağımsız tarama
Tarayıcı, sabit seçici kullanmadan genişlik öncelikli (BFS) dolaşır. Sayfa türü sınıflandırması (ürün, hakkında, blog, lookbook, SSS), URL yolunun bir düzenli ifade sözlüğüne uyumuyla yapılır; böylece alan adına özel mantık olmadan her marka sitesi bu türlere eşlenir. Görsel çıkarımı, modern e-ticaret altyapılarındaki tembel yükleme örüntülerini kapsamak için `src`, `data-src`, `data-lazy-src` ve `srcset` alanlarını işler.

### 2. Çözünürlük eşiği: kısa kenarda en az 512 px
512 px, CLIP için yaygın alt sınırdır (ViT-B/32'nin yerel çözünürlüğü 224 px'tir, ancak model büyük görsellerden alınmış 224–336 px kırpmalarla önceden eğitilmiştir). Kısa kenarı 512 px'in altındaki görseller ya arayüz öğesi, ya süs amaçlı küçük resim ya da çözünürlüğü bozulmuş görsellerdir ve sonraki gömmelere gürültü katar. Daha yükseğe çıkmak (800 px+) görsel ağırlıklı sitelerde geçerli ürün küçük resimlerini eler. 512 px, CLIP'in sonraki görevleri için bilinen dengeli noktadır.

### 3. Kopya ayıklama için algısal karma
URL/MD5 ile kopya ayıklama, aynı görselin birden çok CDN yolundan sunulmasını, yeniden boyutlandırılmış küçük resimleri ve yeniden sıkıştırılmış varyantları kaçırır. pHash (imagehash kütüphanesi) bu durumlarda görsel benzerliği yakalar. Hamming mesafesi ≤ 8 eşiği, neredeyse aynı görselleri ayıklarken arka planı ya da modeli paylaşan gerçekten farklı çekimleri korur.

### 4. İki aşamalı moda sınıflandırma
**Birincil:** 12 aday etikete (olumlu: giysi/kıyafet/model/lookbook/ayakkabı/aksesuar; olumsuz: logo/arayüz/manzara/yemek) karşı CLIP sıfır-örnek sınıflandırma. Eğitim verisi veya modaya özel ince ayar gerektirmez; her marka estetiğine genellenir.
**Yedek:** Alt metin, çevre sayfa metni ve kaynak URL üzerinde anahtar kelime sezgisi. `transformers` kullanılamadığında (ör. kaynakları kısıtlı CI ortamları) devreye girer; daha düşük kesinlikle de olsa hattın çalışmasını sürdürmeye yeter.

### 5. Metin sentezi için LLM sağlayıcı kademesi
Öncelik sırasıyla üç sağlayıcı:
1. **Groq** (ücretsiz, llama3-70b-8192, ~200 ms gecikme): varsayılan kullanım için önerilir
2. **Ollama** (yerel, llama3.2, sıfır maliyet; yerel kurulum ve disk alanı gerekir)
3. **Anthropic Claude** (ücretli, en yüksek kalite, yedek olarak kullanılır)

Hiçbirine ulaşılamazsa görsel analiz tam çalışır, yalnızca metin sentezi bölümleri "kullanılamıyor" olarak işaretlenir. Bu, hattın her yapılandırmada kısmi değer sunabilmesini sağlar.

Neden tek sağlayıcı değil? Maliyet, erişilebilirlik ve kullanıcı kısıtları değişir. Kademeli yaklaşım, ajanın kısıtlı ortamlarda (API bütçesi yok, ağdan yalıtılmış vb.) kod değişikliği olmadan dağıtılabilmesini sağlar.

### 6. Görsel kümeleme için CLIP gömmeleri + KMeans
CLIP, görselleri anlamsal olarak anlamlı 512 boyutlu bir uzaya yansıtır; benzer stil, renk ve konu, modaya özel etiket olmadan doğal olarak kümelenir. KMeans bunları 3–5 kümeye ayırır (küme sayısı `floor(n_images / 20)` ile dinamik belirlenir ve 3–5 aralığına sıkıştırılır). Bu, değişken görsel sayılarında sabit küme sayısından doğan çok küçük ya da aşırı büyük kümeleri önler.

### 7. Ayarlanabilir aralıklı asenkron toplama
Hem tarayıcı hem görsel indirici tamamen asenkrondur (aiohttp + asyncio). Bir semafor eşzamanlı istekleri `MAX_CONCURRENT_REQUESTS` (varsayılan 4) ile sınırlar. Sayfa çekimleri arasına istek başına `REQUEST_DELAY_MS` (varsayılan 800 ms) bekleme konur. Her iki değer `.env` içinde ayarlanabilir; işletenler hedef siteye göre hız ile nezaket arasında denge kurabilir.

### 8. Her aşamada zarif hata yönetimi
Her ana aşama (web taraması, görsel indirme, Instagram, LLM sentezi) try/except ile sarılıdır. Hatalar `[warning]` veya `[error]` düzeyinde yapılandırılmış olay olarak kaydedilir ve hat devam eder. Instagram'ı engelli ve LLM'i kesintide olan bir marka için bile görsel verili geçerli bir PDF üretilir. Bu bilinçli bir tasarım tercihidir: kısmi değer, çökmeden her zaman daha iyidir.

### 9. Instagram hız sınırı: tasarım kararı ve hafifletme
`instaloader` oturumsuz, herkese açık modda kullanılır. Instagram, oturumsuz erişimde sert hız sınırı uygular (genellikle 10–15 istekten sonra HTTP 429). Ajan:
- 429'u yapılandırılmış bağlamla kaydeder: `instagram_collection_failed reason=429 handle=<kullanıcı>`
- Instagram'ı atlar ve web sitesi verisiyle devam eder
- Bunu README'de bot önleme bölümü altında açıkça belgeler

Üretim için hafifletmeler (uygulanmamıştır, şeffaflık için belgelenmiştir):
- **Oturumlu kimlik doğrulama:** `instaloader` oturum dosyası enjeksiyonunu destekler; giriş yapılmış oturum hız sınırını belirgin biçimde yükseltir
- **Jitter'lı üstel geri çekilme:** rastgele gecikmelerle yeniden deneme
- **Dönen proxy'ler:** istekleri dağıtmak için konut IP döndürme
Bunlar yüksek hacimli kullanım için doğal sonraki iterasyonlardır.

## Ödünleşimler

| Karar | Artı | Eksi |
|---|---|---|
| CLIP sıfır-örnek | Eğitim verisi gerekmez, markadan bağımsız | İnce ayarlı modelden düşük kesinlik |
| Varsayılan LLM olarak Groq | Ücretsiz, hızlı, kredi kartı yok | Yüksek hacimde hız sınırı |
| BFS tarayıcı | Basit, öngörülebilir | JS ile çizilen ürün listelerini kaçırır |
| Playwright yok | Daha basit, daha hızlı | React/Next.js mağazalarını kaçırır |
| instaloader | API anahtarı gerekmez | Instagram hız sınırlarına kırılgan |
| pHash kopya ayıklama | CDN/boyut varyantlarını yakalar | Anlamsal olarak aynı çekimleri kaçırabilir |

## Daha fazla zaman olsaydı neler değişirdi

**Daha yüksek öncelik:**

1. **Playwright entegrasyonu:** Birçok doğrudan tüketiciye satış yapan marka Next.js veya Shopify Hydrogen kullanır. `WebsiteCrawler` içinde başsız tarayıcı yedeği bunları kazandırır. Mimari temiz bir enjeksiyon noktası sunar: tarayıcı, çekme yönteminden bağımsız olarak `PageContent[]` döndürür.

2. **İnce ayarlı moda sınıflandırıcı:** DeepFashion2 üzerinde eğitilmiş hafif bir ViT, ikili (moda/moda değil) yerine kesin giysi düzeyinde etiketler vererek daha zengin bir giysi karması verisi üretir. `FashionClassifier` sınıfı doğrudan yerine konabilecek biçimde tasarlanmıştır.

3. **Instagram oturum kimlik doğrulaması:** instaloader ile oturum çerezi eklemek, pratik hız sınırını çalıştırma başına ~15'ten yüzlerce gönderiye çıkarır. Tek bir `.env` değişkeni (`INSTAGRAM_SESSION_FILE`) yeterli olur.

4. **Vektör deposuyla kopya ayıklama:** 10 bin+ görselde pHash taraması yavaşlar. CLIP gömmeleri üzerinde FAISS veya Qdrant, bunu doğrusal altı aramayla değiştirir.

5. **Yapılandırılmış önbellek:** Aynı markaya yeniden çalıştırmada zaten indirilmiş görseller atlanmalıdır. URL karmasıyla anahtarlanan bir SQLite deposu ikinci çalıştırma süresini yaklaşık %80 kısaltır.

## Binlerce marka için işletim

- Ajanı bir görev kuyruğuna (Celery + Redis veya AWS SQS) sarın. Her marka yapılandırması bir mesajdır.
- Çıktıları `marka_slug/run_id/` anahtarıyla nesne depolamada (S3/GCS) saklayın.
- CLIP çıkarımını GPU toplu uç noktasına (Replicate veya kendi barındırdığınız Triton) taşıyın; ölçekte gömme hesabı G/Ç'nin önüne geçer.
- Çalıştırmalar arasında değişmeyen varlıkları yeniden indirmemek için sayfaları ve görselleri içerik adresli depoda önbelleğe alın.
- Maliyet kontrolü için LLM çağrılarını parametreleyin: ilk geçiş sentezi için Groq, kalitenin en çok önem taşıdığı son konumlandırma ifadeleri için yalnızca Claude.
- Yapılandırılmış günlükleri (structlog ile zaten mevcut) bir günlük toplayıcıya gönderin; SLA izleme için marka başına metrikleri (görsel sayısı, taranan sayfa, çalışma süresi) zaman serisi deposuna yazın.