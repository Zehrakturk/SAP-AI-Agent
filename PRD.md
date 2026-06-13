# PRD — SAP-AI Copilot
**Ürün:** SAP + AI Tabanlı Karar Destek & Veri Entegrasyon Platformu
**Sürüm:** 3.0 · **Tarih:** 2026-06 · **Durum:** Aktif geliştirme (Sprint 1–4 + Human-in-the-loop + Çok-Kiracılık + PDF-RAG + Canlı SAP Sorgu + Semantic Layer + Veri Yaşam Döngüsü tamamlandı)

> **v3.0 yenilikleri:**
> - **Canlı (anlık) SAP sorgu:** Belirli entegrasyonlar (örn. SAS) SQL'e yazmadan soru-anında SOAP'tan
>   çekilir; `EV_SUCCESS/EV_MESSAGE` ile başarı/hata gösterilir, `ET_RETURN` analiz edilir.
> - **Oturum-bazlı drill-down önbelleği:** Aynı veri seti üzerine takip soruları SAP'a tekrar gitmeden
>   önbellekten filtrelenir ("aynı malzeme" → önceki odak çözümü).
> - **Satıcı adı eşleme:** `ET_RETURN_VENDOR` ile satıcı kodu → ad eşleştirilir; kullanıcıya **ad** gösterilir.
> - **Semantic Layer (metrik sözlüğü):** iş terimi → SQL ifadesi; admin **Metrikler** sayfası; cevaplarda 📐 kullanılan metrikler.
> - **Veri Yaşam Döngüsü:** rollup (günlük özet) + retention + PAGE sıkıştırma + artımlı (watermark) çekme → SQL şişmez.
> - **Çıktı modu:** "göster/grafik/rapor" denmedikçe **kısa metin cevap** (grafik/KPI üretilmez).
> - **Gerçek token logu** (OpenAI `.usage`), OpenAI kota hatasında **zarif mesaj**, Türkçe iş terimleriyle yanıt,
>   `.env` önceliği (`load_dotenv(override=True)`), güvenlik temizliği (iç hostname → `.env`).
>
> **v2.0:** Çok-kiracılık (Warmhaus / Beyçelik), girişte firma seçici, PDF-RAG (**Belgeler**),
> rapor↔bilgi yönlendirme, akıllı takip soruları, **Çıkış Yap** butonu, Gemini `gemini-3.1-flash-lite`.

---

## 1. Doküman Amacı
Bu PRD, SAP-AI Copilot'un mevcut işlevlerini, mimarisini, veri modelini, API'sini, güvenlik
durumunu ve yol haritasını tek kaynakta toplar. Hedef kitle: geliştiriciler, ürün sahibi,
yeni katılan ekip üyeleri ve teknik karar vericiler.

---

## 2. Ürün Özeti & Vizyon
Kullanıcının doğal dilde (Türkçe) sorduğu soruları SAP verisine dayalı T-SQL'e çevirip
analiz + görselleştirme üreten; ayrıca kullanıcı sormadan **proaktif içgörü** çıkaran ve
sistemde **eksik veriyi insan onayıyla SAP'tan çekebilen** bir karar destek asistanı.
Sistem **çok-kiracılıdır** (her firma yalnız kendi verisini görür) ve **iki bilgi kaynağını**
ayırır: yapısal SAP verisi (rapor/sayı soruları → SQL) ve **yüklenen PDF belgeler** (nasıl
yapılır / hata çözümü / yol haritası soruları → PDF-RAG).

**Vizyon:** "Reaktif sorgu aracı" → "proaktif, kendi kendine veri tamamlayan dijital analist".

**Çözdüğü problem:** SAP verisine erişim teknik bilgi (SQL, RFC, tablo adları) gerektirir;
analiz manuel ve yavaştır. Bu platform doğal dil + otomatik içgörü ile bu engeli kaldırır.

### 2.1 Sistem Nasıl Çalışır (Uçtan Uca)
0. Kullanıcı giriş ekranında **firmasını seçer** (Warmhaus / Beyçelik / Admin); token'a firma
   gömülür ve bundan sonra tüm veri/belge/onaylar firma bazında izole edilir.
1. Kullanıcı sohbet ekranına Türkçe bir soru yazar: *"Nisan ilk hafta sevkiyatlarını şehir bazında göster."*
2. **Soru yönlendirme (intent classify):** Soru "rapor/veri" mi yoksa "bilgi/nasıl yapılır" mı?
   - **Bilgi** ("bu hatayı nasıl çözerim", "ne yapmalıyım", "yol haritası") → **PDF-RAG** hattına gider.
   - **Veri/rapor** → aşağıdaki SQL hattına devam.
3. Soru OpenAI ile embed edilir; **Qdrant**'ta en alakalı (firmaya ait) entegrasyon şema(lar)ı bulunur (RAG).
4. **Intent parser** soruyu yapılandırır (tarih aralığı, metrik, gruplama, filtre).
5. **GPT-4o** şema + niyet bağlamıyla güvenli bir T-SQL SELECT üretir; `_is_safe_sql` denetler.
6. Sorgu **MSSQL**'de çalışır. Sonuç varsa GPT analiz metni + KPI + Chart.js grafiği + **3 akıllı
   takip sorusu** üretir; **Gemini** arka planda görseli/raporu zenginleştirir.
7. Sonuç yoksa **Human-in-the-loop** devreye girer: kullanıcıya "Bu veri yok, entegrasyon
   çalışsın mı?" sorulur → Evet → admin onayı → onaylanınca SAP'tan çekilir → sorgu otomatik
   yeniden çalışır → cevap teslim edilir.
8. **PDF-RAG hattı (bilgi sorusu):** Soru embed → firmaya ait belge koleksiyonunda (Qdrant
   `SAP-AI-DOCS`) arama → ilgili pasajlar GPT-4o'ya verilir → adım adım Türkçe cevap + **📄 Kaynaklar**
   (dosya adı/snippet) + takip soruları. Firmaya ait belge yoksa "Belgeler sayfasından yükleyin" denir.
9. Gece arka planda **proaktif içgörüler** üretilir; kullanıcı ertesi sabah ana sayfada
   "geçen haftaya göre %23 düşüş + olası sebepler" gibi kartları sormadan görür.

### 2.2 Örnek Senaryolar
- **Karşılaştırma:** *"Nisan 1. hafta ile 2. haftayı kıyasla"* → gruplu bar grafik + "Olası
  Sebepler" (hangi müşteri/şehir/rota değişimi sürükledi).
- **Eksik veri:** *"Mart ayı verileriyle rapor yap"* (veri yok) → onay kartı → admin onayı →
  SAP'tan Mart çekilir → rapor otomatik gelir.
- **Proaktif:** Sabah ana sayfa → *"⚠️ Sevkiyat %23 ↓ — İstanbul rotasında 12 gecikme,
  BATUHAN SARI siparişi %83 düştü"* (kullanıcı hiçbir şey sormadan).
- **Korelasyon:** Satış + sevkiyat entegrasyonu birlikteyken → *"🔗 İkisi de düştü,
  0.78 korelasyon — sevkiyat gecikmesi satış kaybının sebebi olabilir."*
- **Bilgi (PDF-RAG):** *"Sevkiyat entegrasyonu 22018 hatası verirse ne yapmalıyım?"* →
  yüklenen PDF kılavuzdan adım adım cevap + 📄 Kaynaklar kutusu.
- **Firma izolasyonu:** `warmhaus` girişi yalnız `shipments` verisini ve Warmhaus belgelerini
  görür; `beycelik` girişi yalnız kendi entegrasyon/belgesini görür; `admin` hepsini görür.
- **Canlı SAP sorgu + drill-down (SAS):** *"2023 mali yılında birim fiyatı en yüksek malzemem ne?"*
  → SAP'tan o an çekilir (SQL'e yazılmaz), en yüksek birim fiyatlı malzeme döner. Ardından
  *"bu malzemeyi hangi satıcıdan aldım?"* ve *"aynı malzemeyi başka satıcıdan aldım mı?"* →
  **SAP'a tekrar gidilmeden** önbellekten cevaplanır; satıcı **kodu yerine adı** gösterilir.
- **Metin vs görsel:** *"Nisan'da kaç sevkiyat var?"* → kısa metin cevap (grafik yok).
  *"...grafikle göster / rapor hazırla"* denirse → tam grafik + KPI üretilir.

---

## 3. Hedef Kullanıcılar & Roller
| Rol | Örnek | id | Firma | Yetkiler |
|-----|-------|----|-------|----------|
| **ADMIN** | `admin` | 1 | `ALL` (global) | Tüm firmaların sorgu/entegrasyon/belge yönetimi + veri çekme onayı (approve/reject) + tüm ayarlar |
| **USER** | `warmhaus` | 10 | `Warmhaus` | Kendi firmasının sorgu/rapor/belge/içgörüsü; onay talebi açar, admin onayı bekler |
| **USER** | `beycelik` | 11 | `Beycelik` | Kendi firmasının sorgu/rapor/belge/içgörüsü; onay talebi açar |
| **VIEWER** | `p.frank` | 8 | `ALL` | Salt-okur; sorgu sorar, rapor/içgörü görür; onay veremez, entegrasyon yönetemez |

**Çok-kiracılık modeli:** Her kullanıcının bir `company` alanı vardır. `company in (ALL, None)`
olan kullanıcı **global**dir (filtre uygulanmaz). Diğerleri yalnız kendi firmasının
entegrasyon/veri/belge/onaylarını görür. Firma ayrımı token'a (`demo-token-{id}-{role}-{company}`)
gömülür ve her API isteğinde `app/services/tenant.py` üzerinden okunur.

**Personalar:** Lojistik müdürü (sevkiyat/rota odaklı), Satış müdürü (müşteri/sipariş),
Üst yönetim (özet/KPI). Kişiselleştirme motoru, kullanıcının geçmiş sorgularına göre
içgörüleri önceliklendirir (lojistikçiye lojistik, satışçıya satış içgörüsü öne çıkar).

---

## 4. Kapsam
**Dahil (tamamlanan):**
- **Çok-kiracılık:** Firma bazlı giriş (Warmhaus/Beyçelik/Admin) + veri/belge/içgörü izolasyonu
- **Soru yönlendirme:** Rapor/veri → SQL hattı, bilgi/nasıl-yapılır → PDF-RAG hattı
- **PDF-RAG bilgi tabanı:** PDF yükle (**Belgeler** sayfası) → firmaya özel belge embedding →
  belgelerden kaynaklı Türkçe cevap (📄 Kaynaklar)
- Doğal dil → T-SQL sorgu (RAG destekli), firma-scoped
- **Akıllı takip soruları:** her cevabın altında o veriye/bilgiye özel 3 tıklanabilir devam sorusu
- Çok-turlu sohbet (son 3 mesaj bağlamı, "aynısını Mart için" çözümü)
- Proaktif içgörü motoru (5 detector + hipotez üretimi), firma-scoped
- Cross-integration korelasyon (sevkiyat × satış vb.)
- 4 formatlı + interaktif raporlama (kolon/grafik/satır seçimi)
- Server-side PDF/HTML + e-posta paylaşımı
- Dinamik SOAP/REST/OData veri çekme (Factory pattern)
- Human-in-the-loop onaylı veri tamamlama (eksik veri → kullanıcı onayı → admin onayı → otomatik çekme),
  oturum bazlı kalıcı onay kartları
- Sohbet etiketleme + arama + sabitleme; **kullanıcı bazlı + sahiplik korumalı** sohbet geçmişi
- Görünür **Çıkış Yap** butonu → tam sayfa yenilemeden login ekranına dönüş (firma değiştirme)
- **Canlı (anlık) SAP sorgu modu** (entegrasyon bazlı `live_query` bayrağı): SQL'e yazmadan
  soru-anında SOAP çekme + `EV_SUCCESS/EV_MESSAGE` + `ET_RETURN_VENDOR` satıcı adı eşleme
- **Oturum-bazlı drill-down önbelleği:** takip sorularında SAP'a tekrar gitmeden filtreleme
- **Semantic Layer:** metrik sözlüğü (iş terimi → SQL) + admin **Metrikler** sayfası + prompt enjeksiyonu
- **Veri Yaşam Döngüsü:** rollup + retention + PAGE sıkıştırma + artımlı (watermark) çekme
- **Çıktı modu yönetimi:** text (varsayılan) / table / report — görseller yalnız istenince
- **Gözlemlenebilirlik:** gerçek token kullanımı logu (OpenAI `.usage`), kota hatasında zarif mesaj

**Hariç (şu an kapsam dışı):**
- Gerçek JWT/SSO kimlik doğrulama, satır-seviyesi RBAC (demo token kullanılıyor)
- Çoklu-dil arayüz, mobil uygulama
- Taranmış (image-only) PDF'lerde OCR (yalnız metin-tabanlı PDF desteklenir)
- Daily Brief / zamanlanmış rapor aboneliği (Sprint 5)
- Multi-model routing (soru tipine göre farklı model)

---

## 5. Teknoloji Mimarisi
**Backend:** Python + Flask (app factory `create_app`), Flask-CORS, APScheduler (arka plan işleri).
**Frontend:** Vanilla JavaScript SPA (modül başına `static/*.js`), Chart.js görselleştirme, statik HTML şablon.
**Veri katmanı:** MSSQL (`ZehraTestDB`, ODBC Driver 18, pyodbc) + Qdrant vektör DB
(şema koleksiyonu `SAP-AI` + belge koleksiyonu `SAP-AI-DOCS`).
**AI servisleri:**
- OpenAI **GPT-4o** — NL→SQL üretimi + analiz/yorum + PDF-RAG cevap üretimi
- OpenAI **text-embedding-3-small** — RAG embedding (1536 boyut, cosine; hem şema hem belge)
- Google **Gemini `gemini-3.1-flash-lite`** — rapor & görsel zenginleştirme (env ile override edilebilir)

**PDF işleme:** `pypdf` (saf-Python metin çıkarımı; taranmış PDF'ler desteklenmez).
**SAP erişimi:** SOAP (Zeep), REST (requests), OData — `FetcherFactory` ile pluggable.

**Tasarım desenleri:**
- **Factory:** `FetcherFactory` (SOAP/REST/OData), `InsightDetectorFactory` (detector registry)
- **Strategy:** auth (Basic/Bearer/APIKey/None), normalizer (SAP envelope / REST JSON), param_mapper
- **Repository:** insights, ingestion (approval/job/audit), integrations, documents
- **Multi-tenancy:** `tenant.py` yardımcıları her istekte token'dan firma/rol/kullanıcı çıkarır;
  repository ve servis katmanı `company` parametresiyle filtreler.

**Katmanlar:** API (Flask blueprints) → Services (`query_engine`, `doc_rag`, `tenant`, `fetchers`,
`insights`, `ingestion`, `report_renderer`, `email_sender`, `gemini_enhancer`) → Repositories → MSSQL/Qdrant.

```
Kullanıcı (firma seçer) → Flask API → tenant.company_from_request
                              │
                              ▼
                         query_engine.ask(company=...)
                              │
        ┌── classify_intent ──┤
        │ (bilgi)             │ (veri/rapor)
        ▼                     ▼
   doc_rag ──> Qdrant     query_engine ──RAG──> Qdrant (firma şemaları)
   (SAP-AI-DOCS,               │
    firma filtreli)            ├─> MSSQL (firma-scoped T-SQL)
        │                      ├─> GPT-4o (SQL + analiz + takip soruları)
        └─> GPT-4o cevap       ├─> Gemini (zenginleştirme)
            + 📄 kaynaklar     └─> ingestion (eksik veri → onay → SAP fetch → rerun)
APScheduler ──> fetch_all_active (02:00) / generate_insights (03:00) / process_pending_jobs (5 sn)
```

---

## 6. Fonksiyonel Modüller

### 6.1 Kimlik & Çok-Kiracılık (auth + tenant)
Demo login: kullanıcı/şifre doğrulanır → `demo-token-{id}-{role}-{company}` döner. Giriş ekranında
**firma seçici** (Warmhaus 🔥 / Beyçelik ⚙️ / Admin 🛡️) kullanıcı adını otomatik doldurur.
Rol/firma/kullanıcı her istekte `app/services/tenant.py` ile token'dan okunur
(`company_from_request`, `role_from_request`, `is_global`, `is_admin`). `app/models/store.py`
`company_of(user_id)` yardımcısı firma çözümler. **Çıkış Yap** butonu sidebar'ın altında görünür;
tıklanınca token temizlenir ve login ekranına dönülür (tam sayfa yenilemeden → firma değiştirme kolay).

### 6.2 Sorgu Motoru (query_engine)
**Soru yönlendirme:** `ask()` başında `classify_intent` çalışır — bilgi sorusu ise
`doc_rag.answer_question(question, company)` döndürülür (PDF-RAG); veri sorusu ise SQL hattı işler.
SQL hattı: RAG (soru embed → Qdrant'ta **firmaya ait** şema ara) → intent parse (tarih/metrik/grup) →
T-SQL üret → güvenlik denetimi (`_is_safe_sql`, yalnız SELECT/WITH) → MSSQL'de çalıştır → GPT analiz +
Chart.js paketi (KPI, highlights, primary/secondary grafik) + **3 akıllı takip sorusu** (`follow_ups`).
Tüm RAG/şema seçimi `company` parametresiyle firmaya kısıtlanır. Çok-turlu: son 3 mesaj bağlama
girer. Karşılaştırma sorgularında otomatik "Olası Sebepler" (hipotez) kutusu. 0 satır dönerse
Human-in-the-loop akışını tetikler.

### 6.2b PDF-RAG Bilgi Tabanı (doc_rag)
`index_pdf(file_bytes, filename, company, uploaded_by)`: pypdf ile metin çıkar → ~1500 karakterlik
parçalara böl → `text-embedding-3-small` ile embed → Qdrant `SAP-AI-DOCS` koleksiyonuna firma payload'lı
upsert + `documents` tablosuna kayıt. `answer_question(question, company)`: soruyu embed → **firma
filtreli** vektör arama (`query_points`) → top-k pasaj → GPT-4o JSON modunda Türkçe cevap + 3 takip
sorusu üretir, dosya bazında benzersiz **kaynak** listesi döner. Belge yoksa "Belgeler sayfasından
yükleyin" mesajı. `classify_intent`: anahtar-kelime (knowledge/data) + belirsizse ucuz LLM kararı.

### 6.2c Canlı (Anlık) SAP Sorgu + Drill-down Önbelleği (query_engine + orchestrator)
Bir entegrasyon `extra_config.live_query=true` ile işaretliyse (örn. **SAS Servisi**), o entegrasyona
ait sorular **SQL'e yazılmadan** soru-anında SOAP'tan çekilir. Yönlendirme `_route_live`: firma-kapsamlı
+ anahtar-kelime (satınalma/satıcı/malzeme/mali yıl…) + yedek olarak parametre-çıkarımı (RAG'a bağımlı
değil). Akış: LLM sorudan parametreleri çıkarır (`_extract_live_params`) → normalizasyon
(`_normalize_live_params`: "2023" → `2023001` 7-haneli FISCPER) → `query_integration_live` SOAP çağrısı
(tüm `IV_*` parametreleri boş bile olsa gönderilir) → `ET_RETURN` analiz, `EV_SUCCESS/EV_MESSAGE` gösterilir.
**Satıcı adı:** `ET_RETURN_VENDOR` tablosundan kod→ad eşlemesi (`_build_vendor_name_map`) yapılır,
kayıtlara `SATICI_ADI` eklenir; kullanıcıya satıcı **kodu yerine adı** gösterilir.
**Sıralama:** "en yüksek/düşük birim fiyat" gibi sorularda binlerce kayıtta truncation olmasın diye
mevcut alana (PRICE/AMOUNT) göre Python'da sıralanır. **Drill-down önbelleği** (`_LIVE_CACHE`,
oturum-bazlı): aynı oturumda uyumlu bir veri seti çekildiyse takip soruları **SAP'a gitmeden**
önbellekten firma-içi filtrelenir; "aynı/bu malzeme" eliptik referansı önceki odaktan (`last_material`) çözülür.

### 6.2d Çıktı Modu (text / table / report)
`_output_mode(question)` kullanıcının niyetini ayırır: "rapor/grafik/görsel/pano" → **report** (tam
grafik + KPI + tablo); "listele/göster/tablo" → **table** (veri tablosu); aksi halde **text** (kısa,
net metin cevap — grafik/KPI üretilmez). Varsayılan **text** olduğundan AI gereksiz görsel üretmez;
yalnız açıkça istenince zengin görselleştirme döner. Hem SQL hem canlı sorgu hattında çalışır.

### 6.2e Semantic Layer (Metrik Sözlüğü)
`semantic_metrics` tablosu iş terimlerini SQL karşılığına bağlar (firma + entegrasyon scope'lu):
`metric_type` = measure (SELECT/aggregate) | filter (WHERE) | dimension (GROUP BY), `expression`,
`synonyms`. `semantic_layer.fetch_for(company, integration_ids)` ilgili metrikleri çeker,
`format_for_prompt` NL→SQL prompt'una **METRİK SÖZLÜĞÜ** bloğu enjekte eder (LLM tanımlı ifadeyi
aynen kullanır → tutarlı KPI), `detect_used` soruda geçen metrikleri bulur → cevapta **📐 Kullanılan
metrikler** çipleri. Admin **Metrikler** sayfasından (`static/metrics.js`, `/api/v1/metrics`) ekle/
düzenle/sil/aktifleştir. Seed: shipments ölçüleri (aktif) + durum/gecikme filtreleri (taslak).
Önemli kural: metrik ifadeleri **ham tablolar** içindir; rollup tablosu kullanılırsa onun kendi
ölçü kolonları (shipment_count, total_qty…) kullanılır.

### 6.2f Veri Yaşam Döngüsü (lifecycle) — SQL şişmesini engeller
Yeni `app/services/lifecycle/` paketi:
- **compression:** fact + rollup tablolarına idempotent `PAGE` sıkıştırma (zaten PAGE ise atlar).
- **watermark:** artımlı çekme — hedef tablodaki `MAX(tarih)`'ten itibaren yalnız yeni veri
  (`incremental_params`); `fetch_all_active(incremental=True)` bunu kullanır, tarih param'ı olmayan
  entegrasyonlar eski davranışa düşer.
- **rollup:** ham fact → günlük özet tabloları (`shipments_daily` …): gun + integration_id + company +
  boyutlar + ölçüler. Pencere için idempotent (DELETE+INSERT), eski rollup'a dokunmaz (birikimli).
  `rollup_hint_for` query_engine prompt'una "trend/eski-dönem → rollup" kuralını enjekte eder.
- **retention:** `HOT_WINDOW_MONTHS` (vars. 6) dışı ham satırları temizler — **önce** silinecek
  pencereyi rollup'lar, sonra siler (kalıcı özet korunur). Varsayılan **KAPALI** (`RETENTION_ENABLED=0`).
- `run_nightly_maintenance()` gece 02:30 çalışır (rollup → retention). `data/optimize_storage.py`
  tek-seferlik kurulum (sıkıştır + rollup oluştur + backfill). `/api/v1/lifecycle/status` (admin):
  tablo satır/boyut/sıkıştırma + watermark özeti.

### 6.3 Entegrasyonlar (fetchers)
SOAP/REST/OData fetcher'ları; 5 hazır şablon (SAP SOAP, REST satış, CRM, SAP OData, custom);
şema indeksleme (Qdrant); manuel veri çekme; `fetch_log` ile (integration_id, param_hash) cache.
Her entegrasyon bir **firmaya** aittir (`integrations.company`): `shipments`→Warmhaus,
`Press Raporu`/`Sevkiyat Servisi`→Beycelik. Listeleme/oluşturma firma bazında filtrelenir/damgalanır.
Veri yazıcı (`data_writer`) tip-duyarlı dönüştürme (tarih/decimal/int) + PK varsa MERGE (upsert),
yoksa DELETE+INSERT yapar; `schema_builder` mevcut tablolara sistem kolonlarını (param_hash,
integration_id, fetched_at) idempotent ALTER ile ekler.

### 6.3b Belgeler (documents / PDF yükleme)
Yeni **Belgeler** sayfası (`static/documents.js`): sürükle-bırak veya dosya seçerek PDF yükleme,
firma belgelerini listeleme (ad, sayfa, tarih), silme. Yüklenen PDF `doc_rag.index_pdf` ile
embed edilir; yalnız yükleyen firma kendi belgelerini görür (firma izolasyonu).

### 6.4 İçgörü Motoru (insights)
Detector'lar: `trend_change` (hafta/ay karşılaştırma), `top_mover` (en çok yükselen/düşen),
`stuck_record` (takılı TDURUM), `anomaly` (freshness/volume drop), `correlation` (iki entegrasyon
arası Pearson + lag). Hypothesis engine: dimension breakdown + GPT ile kök-sebep önerisi.
Kişiselleştirme: geçmiş sorgu profili + manuel ilgi alanlarıyla sıralama.
İçgörü üretimi de firma-scoped çalışır (`metric_calculator.list_active_integrations(company)`).

### 6.5 Raporlama (reports)
4 format: Yönetici Panosu, Analiz Raporu, Veri Tablosu, Trend Raporu. İnteraktif oluşturucu:
kullanıcı kolon/grafik ekseni/grafik tipi/satır limiti seçer. Server-side HTML/PDF (WeasyPrint
varsa PDF, yoksa HTML) + SMTP ile e-posta paylaşımı.

### 6.6 Human-in-the-loop (ingestion)
Eksik veri tespiti → **kullanıcı onayı** ("Mart için entegrasyon çalışsın mı? Evet/Hayır") →
Evet → **admin onayı** → onaylanınca kuyruğa job → worker: fetch → (koşullu) index → rerun
(talep sahibinin firmasıyla) → sonuç otomatik kullanıcıya teslim. Onay kartları `session_id` ile
oturuma bağlı kalır (sayfa yenilense de görünür). Admin'e gerçek-zamanlı **bildirim çanı** (12 sn
polling) düşer. Tüm geçişler append-only `audit_log`'da. Dedup, retry (exponential backoff),
atomik job claim, stale-lock kurtarma.

### 6.7 Ayarlar / Kullanıcılar / Loglar / Analitik
Model ayarları (in-memory), kullanıcı listesi, AI log akışı, kullanım metrikleri.
**Gerçek token logu:** `query_engine` her OpenAI çağrısının (`.usage`) token'larını thread-local
sayaçta toplar (`_usage_*`); `query.py` log kaydına **gerçek** `tokens` + `prompt_tokens` +
`completion_tokens` + `llm_calls` yazar (eski "satır×10+500" tahmini kaldırıldı). doc_rag (PDF-RAG)
token'ları da aynı sayaca eklenir.
**Kota dayanıklılığı:** OpenAI `insufficient_quota` kalıcı hata olduğundan retry yapılmaz; kullanıcıya
tek anlaşılır mesaj döner (500/stack-trace yerine), `OpenAIQuotaError`.

---

## 6.8 Kod Haritası (Dizin Yapısı)
```
SAP-AI/
├── run.py                       # Giriş noktası — Flask'ı 3000 portunda başlatır
├── .env                         # Kimlik bilgileri (bkz. §9)
├── PRD.md                       # Bu doküman
├── app/
│   ├── __init__.py              # create_app() — blueprint kaydı + APScheduler işleri
│   ├── api/                     # Flask blueprint'leri (HTTP katmanı)
│   │   ├── auth.py  users.py  chats.py  logs.py  analytics.py  settings.py
│   │   ├── query.py             # /query/ask — sohbet girişi (firma + yönlendirme + gerçek token logu)
│   │   ├── integrations.py      # entegrasyon CRUD + şablonlar + indeksleme (firma filtreli)
│   │   ├── documents.py         # PDF yükle/listele/sil + /documents/ask (PDF-RAG)
│   │   ├── semantics.py         # /metrics — Semantic Layer CRUD (admin)
│   │   ├── lifecycle.py         # /lifecycle/status|run-maintenance|compress (admin)
│   │   ├── insights.py          # proaktif içgörü + kişiselleştirme
│   │   ├── reports.py           # PDF/HTML export + e-posta
│   │   ├── enhance.py           # Gemini zenginleştirme uçları
│   │   └── approvals.py         # Human-in-the-loop onay API'si
│   ├── services/
│   │   ├── db.py                # merkezi MSSQL bağlantısı (get_connection)
│   │   ├── tenant.py            # çok-kiracılık: firma/rol/kullanıcı + canonical_company
│   │   ├── query_engine.py      # RAG+intent+SQL+analiz+yönlendirme + canlı sorgu + çıktı modu + token sayaç
│   │   ├── doc_rag.py           # PDF-RAG: index_pdf / answer_question / classify_intent
│   │   ├── semantic_layer.py    # Metrik sözlüğü: CRUD + fetch_for/format_for_prompt/detect_used
│   │   ├── lifecycle/           # Veri yaşam döngüsü: compression/watermark/rollup/retention
│   │   ├── qdrant_indexer.py    # şema embedding → Qdrant
│   │   ├── gemini_enhancer.py   # Gemini çağrıları (gemini-3.1-flash-lite)
│   │   ├── report_renderer.py   # HTML→PDF (WeasyPrint)
│   │   ├── email_sender.py      # SMTP gönderici
│   │   ├── fetchers/            # Factory: SOAP/REST/OData veri çekme
│   │   │   ├── core/ (factory, base, result, exceptions)
│   │   │   ├── implementations/ (soap_fetcher, rest_fetcher, odata_fetcher)
│   │   │   ├── strategies/ (auth, normalizers, param_mappers)
│   │   │   ├── persistence/ (data_writer, fetch_logger, schema_builder)
│   │   │   └── orchestrator.py  # fetch_integration / fetch_all_active
│   │   ├── insights/            # Proaktif içgörü motoru
│   │   │   ├── factory, base, models, runner, repository
│   │   │   ├── metric_calculator, hypothesis_engine, correlation_calculator, personalizer
│   │   │   └── detectors/ (trend_change, top_mover, stuck_record, anomaly, correlation)
│   │   └── ingestion/           # Human-in-the-loop
│   │       ├── models, gap_detector, approval_service, job_worker
│   │       └── approval_repository, job_repository, audit_repository
│   ├── repositories/
│   │   └── integration_repository.py   # integrations → IntegrationConfig DTO (firma filtreli)
│   └── models/store.py          # demo USERS(+company), company_of(), SETTINGS, AI_LOGS
├── data/                        # tek-seferlik script'ler (idempotent)
│   ├── migrate_company.py       # integrations.company kolonu + seed
│   ├── configure_sas.py         # SAS canlı entegrasyonu (method/wsdl/şema/keywords/live_query)
│   ├── seed_metrics.py          # Semantic Layer başlangıç metrikleri
│   ├── optimize_storage.py      # sıkıştır + rollup oluştur + backfill (+ opsiyonel purge)
│   └── wsdl/                    # yerel WSDL (iç hostname içerir → .gitignore'da)
├── static/                      # Vanilla JS frontend (sayfa başına modül)
│   ├── chats.js insights.js integrations.js reports.js dashboard.js documents.js metrics.js
│   └── auth.js settings.js users.js logs.js charts.js tables.js api_client.js app.js
├── .env / .env.example          # sırlar (yalnız .env; .gitignore'da) + şablon
└── templates/index.html         # SPA kabuk
```

---

## 7. Veri Modeli (MSSQL — kod tarafından idempotent oluşturulur)
| Tablo | Amaç |
|-------|------|
| `shipments` | SAP sevkiyat verisi (TKNUM, ERDAT, MUSTERI_ADI, CITY1, LFIMG, TDURUM …) — Warmhaus |
| `shipments_daily` | **Rollup (günlük özet):** gun + integration_id + company + boyut/ölçü (retention sonrası eski dönem burada yaşar) |
| `semantic_metrics` | **Semantic Layer:** metrik sözlüğü (metric_key, metric_type, expression, synonyms, company, integration_id, is_active) |
| `integrations` | Entegrasyon tanımları (tip, url, auth, kimlik, **`company`** + `extra_config.live_query`/`keywords`) |
| `documents` | Yüklenen PDF belge meta verisi (id, company, filename, page_count, chunk_count, uploaded_by, uploaded_at) |
| `integration_schemas` | Her entegrasyonun hedef tablo + şema metni (RAG kaynağı) |
| `integration_vectors` | Qdrant point_id ↔ integration eşlemesi + chunk metni |
| `integration_params` | Entegrasyon parametre tanımları (ISTART_DATE vb.) |
| `fetch_log` | (integration_id, param_hash) çekme cache'i |
| `chat_sessions` | Sohbet oturumları (+ `user_id` sahiplik, `tags`, `pinned`) — kullanıcı bazlı, süresiz tutulur |
| `chat_messages` | Sohbet mesajları (rol, içerik, data_json; follow_ups/sources dahil) — sınırsız, tam geçmiş |
| `insights` | Proaktif içgörü kartları |
| `user_preferences` | Kişiselleştirme (ilgi alanları) |
| `approval_requests` | HITL onay talepleri |
| `ingestion_jobs` | HITL veri çekme kuyruğu |
| `audit_log` | Append-only denetim izi (değişmez) |

---

## 8. API Referansı (prefix `/api/v1`, ~90 route)
**auth:** `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
**query:** `POST /query/ask` (HITL aktif), `POST /query/filter`
**chats:** `GET|POST /chats/sessions`, `GET /chats/sessions/<id>`,
`GET|POST /chats/sessions/<id>/messages`, `DELETE /chats/sessions/<id>`,
`PATCH /chats/sessions/<id>/{title|pin|tags}`
**integrations:** `GET|POST /integrations/`, `GET|PUT|DELETE /integrations/<id>`,
`POST /integrations/<id>/schema`, `GET|POST /integrations/<id>/params`,
`POST /integrations/<id>/index`, `GET /integrations/<id>/index-status`,
`POST /integrations/index-all`, `POST /integrations/<id>/fetch`,
`GET /integrations/<id>/fetch-log`, `GET /integrations/templates`
**insights:** `GET /insights/`, `POST /insights/run`, `POST /insights/<id>/view`,
`POST /insights/<id>/dismiss`, `POST /insights/explain`, `GET|PUT /insights/interests`
**reports:** `GET /reports/capabilities`, `POST /reports/export`, `POST /reports/email`
**approvals (HITL):** `POST /approvals/request` (kullanıcı onayı), `GET /approvals/` (admin, PENDING),
`GET /approvals/<id>`, `GET /approvals/by-session/<sid>` (oturum kartları), `POST /approvals/<id>/approve`,
`POST /approvals/<id>/reject`, `GET /approvals/status/<external_id>`, `GET /approvals/jobs/<id>`,
`POST /approvals/run-worker`
**documents (PDF-RAG):** `POST /documents/` (multipart PDF yükle), `GET /documents/` (firma belgeleri),
`DELETE /documents/<id>`, `POST /documents/ask` (belgeye dayalı soru). Tümü firma-scoped.
**metrics (Semantic Layer, admin):** `GET|POST /metrics/`, `GET|PUT|DELETE /metrics/<id>`
**lifecycle (admin):** `GET /lifecycle/status` (tablo boyut/sıkıştırma/watermark),
`POST /lifecycle/run-maintenance` (rollup+retention), `POST /lifecycle/compress`
**enhance:** `GET /enhance/status`, `POST /enhance/{visualization|report|palette}`
**settings:** `GET|PUT /settings/`, `GET /settings/models`, `POST /settings/test-connection`,
`GET /settings/connectors`
**users / logs / analytics:** kullanıcı CRUD, AI log akışı, kullanım metrikleri.

---

## 9. Harici Servisler & Ortam Değişkenleri (.env)

> 🔒 **Güvenlik:** Gerçek değerler yalnızca yerel `.env` dosyasında tutulur (`.gitignore`'da,
> repoya gitmez). Şablon için `.env.example` dosyasına bakın. Aşağıda yalnızca değişken adları
> ve örnek/maskeli değerler verilmiştir.

### 9.1 AI Servis Anahtarları
| Değişken | Örnek | Amaç |
|----------|-------|------|
| `OPENAI_API_KEY` | `sk-...` | GPT-4o + text-embedding-3-small + PDF-RAG |
| `GEMINI_API_KEY` | `AIza...` | Gemini zenginleştirme |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Gemini model adı (override) |

### 9.2 MSSQL Veritabanı
| Değişken | Açıklama |
|----------|----------|
| `DB_SERVER` | MSSQL sunucu IP/host (iç ağ) |
| `DB_NAME` | Veritabanı adı |
| `DB_USER` | DB kullanıcısı |
| `DB_PASS` | DB şifresi (yalnız `.env`) |
| ODBC Driver | `ODBC Driver 18 for SQL Server` (TrustServerCertificate=yes; Encrypt=yes) |

### 9.3 Qdrant Vektör DB
| Değişken | Açıklama |
|----------|----------|
| `QDRANT_URL` | Qdrant endpoint (iç ağ, örn. `http://host:6333`) |
| `QDRANT_COLLECTION` | `SAP-AI` (entegrasyon şemaları) |
| `QDRANT_DOC_COLLECTION` | `SAP-AI-DOCS` (PDF belge parçaları, firma payload'lı) |
| `QDRANT_API_KEY` | _(boş — kimlik doğrulamasız iç ağ)_ |

### 9.4 SAP Bağlantısı & Canlı Sorgu (SAS)
| Değişken | Açıklama |
|----------|----------|
| `SAP_WSDL_URL`, `SAP_SERVICE_METHOD`, `SAP_USERNAME`, `SAP_PASSWORD` | Genel SAP/seed bağlantısı |
| `SAP_SAS_ENDPOINT` | SAS servisi endpoint (iç hostname **koda gömülü değil**, `.env`'de) |
| `SAP_SAS_WSDL_URL` | (ops.) SAS tam WSDL URL; verilmezse `configure_sas` mevcut DB değerini korur |

### 9.5 Veri Yaşam Döngüsü
| Değişken | Vars. | Açıklama |
|----------|-------|----------|
| `HOT_WINDOW_MONTHS` | 6 | Ham veride tutulacak sıcak pencere (ay) |
| `ROLLUP_ENABLED` | 1 | Gece rollup üretimi |
| `RETENTION_ENABLED` | 0 | Eski ham satır temizleme (**veri siler** → varsayılan kapalı) |
| `ARCHIVE_BEFORE_PURGE` | 0 | Purge öncesi arşiv tablosuna kopyala |

### 9.6 E-posta (rapor paylaşımı — opsiyonel)
`SMTP_HOST`, `SMTP_PORT` (vars. 587), `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_TLS` (vars. 1).
Ayarlanmazsa `/reports/email` 503 döner.

> ⚙️ **`.env` önceliği:** `load_dotenv(override=True)` ile `.env`, sistem ortam değişkenlerini
> **ezer** (örn. Windows'ta kalmış eski `OPENAI_API_KEY`). Böylece `.env`'i güncellemek yeterlidir.

### 9.5 Model Konfigürasyonu (opsiyonel override)
`SQL_MODEL` (vars. `gpt-4o`), `ANALYSIS_MODEL` (vars. `gpt-4o`), `GEMINI_MODEL` (vars. `gemini-3.1-flash-lite`).
Embedding sabit: `text-embedding-3-small` (1536 boyut, hem şema hem belge için).

> **Uyumsuzluk notu:** Çalışan modeller GPT-4o/Gemini iken `app/api/settings.py` `AVAILABLE_MODELS`
> Claude modellerini listeler (kozmetik UI tutarsızlığı, işlevi etkilemez).

---

## 10. Erişim Bilgileri (Admin / Kullanıcı)
**Uygulama:** `http://localhost:3000` — başlat: `python run.py`

| Kullanıcı | Şifre | Rol | id | Firma | Departman |
|-----------|-------|-----|----|-------|-----------|
| `admin` | `admin123` | ADMIN | 1 | ALL (global) | IT |
| `warmhaus` | `warm123` | USER | 10 | Warmhaus | Lojistik |
| `beycelik` | `bey123` | USER | 11 | Beycelik | Üretim |
| `p.frank` | `view123` | VIEWER | 8 | ALL | Management |

- **Token formatı:** `demo-token-{id}-{role}-{company}` → admin için `demo-token-1-ADMIN-ALL`,
  warmhaus için `demo-token-10-USER-Warmhaus`. Girişte firma kartı seçilir, kullanıcı adı otomatik dolar.
- **Altyapı kimlikleri:** DB/API/Qdrant gerçek değerleri yalnız yerel `.env` dosyasındadır
  (repoya gitmez). Demo kullanıcı şifreleri `app/models/store.py` `USERS` içinde (demo amaçlı).

---

## 11. Güvenlik — Mevcut Durum & Bulgular
**Mevcut güçlü yanlar:**
- SQL allow-list denetimi (`_is_safe_sql`) — yalnız SELECT/WITH, DML/DDL engelli
- HITL admin onayı + append-only `audit_log` (tam izlenebilirlik)
- Onay polling'inde PII sahip izolasyonu (sonuç yalnız talebi açana)
- Liste görünümünde şifre/NVARCHAR(MAX) kolonları hariç tutulur

**Riskler ve öneriler:**
- 🟢 **Sır yönetimi (düzeltildi):** Gerçek sırlar yalnız yerel `.env`'de; `.gitignore` ile
  repodan hariç, `.env.example` şablon olarak commit'li, `store.py` artık env'den okuyor.
  İç SAP hostname'i koddan kaldırıldı → `SAP_SAS_ENDPOINT` (`.env`); `data/wsdl/` `.gitignore`'da.
  Commit öncesi tam sızıntı taraması yapıldı: API key / DB / SAP şifresi kodda **yok**.
  ⚠️ `.env` daha önce commit'lendiyse git geçmişinden temizlenmeli ve anahtarlar **rotate** edilmeli
  (özellikle bir kez sızan SAP parolası).
- 🟠 **Demo kullanıcı şifreleri:** `store.py` `USERS` içinde düz metin (admin123 vb.) — demo amaçlı;
  üretimde hash + gerçek kullanıcı tablosu gerekir.
- 🔴 **Demo kimlik doğrulama:** Parolalar düz metin, token kolayca taklit edilebilir
  (`demo-token-1-ADMIN` elle yazılabilir). → Gerçek JWT + parola hash (bcrypt).
- 🟠 **SQL injection yüzeyi:** Filtre/karşılaştırma değerleri bazı yollarda WHERE'e string
  interpolasyonla giriyor. → Parametreli sorgulara geçir.
- 🟠 **CORS `*`** ve token-string seviyesinde RBAC. → Origin kısıtla, yetki katmanını güçlendir.

---

## 12. Arka Plan İşleri (APScheduler)
| Zaman | İş |
|-------|-----|
| 02:00 | Tüm aktif entegrasyonlardan **artımlı** veri çek (`fetch_all_active`; canlı entegrasyonlar atlanır) |
| 02:30 | Veri yaşam döngüsü bakımı (`run_nightly_maintenance`: rollup → retention) |
| 03:00 | Proaktif içgörü üret (`generate_insights`) |
| Her 5 sn | HITL ingestion worker (`process_pending_jobs`) |

---

## 13. Kurulum & Çalıştırma
1. Şirket ağına bağlan (MSSQL + Qdrant + SAP erişimi iç ağda; gerçek host/IP'ler **yalnız `.env`**'de).
2. `.env` dosyasını doldur (§9) — `.env.example`'ı kopyalayıp gerçek değerleri gir.
3. Bağımlılıklar: `Flask`, `flask-cors`, `apscheduler`, `openai`, `qdrant-client`, `zeep`,
   `pyodbc`, `python-dotenv`, `pypdf`, `google-generativeai`, (opsiyonel PDF için) `weasyprint`.
4. `python run.py` → `http://localhost:3000` (giriş: `admin / admin123` veya firma kullanıcısı).
5. (Tek seferlik, opsiyonel) `python data/optimize_storage.py` (sıkıştırma + rollup),
   `python data/seed_metrics.py` (metrikler), `python data/configure_sas.py` (canlı SAS).

---

## 14. Bilinen Sınırlamalar
- WeasyPrint kurulu değilse rapor PDF yerine HTML iner.
- E-posta `SMTP_*` ayarlanmadan çalışmaz (503 döner).
- Korelasyon içgörüsü için en az 2 entegrasyonda son 30 günde günlük veri gerekir.
- Taranmış (image-only) PDF'lerden metin çıkarılamaz (OCR yok) → "metin bulunamadı" uyarısı.
- Kimlik/RBAC demo seviyesinde (bkz. §11); firma izolasyonu token tabanlıdır.
- **Canlı sorgu (SAS):** SAP'a anlık bağımlıdır (ağ/kimlik gerekir); rollup `shipment_count`
  gibi tekil sayımlar boyutlara bölündüğü için **yaklaşık**tır (kesin tekil sayım ham tablodan).
  Mali yıl tek bir 7-haneli `FISCPER` dönemine eşlenir (bu BW modelinde yıllık veri `001`'de).
- Drill-down önbelleği **oturum (session_id) bazlıdır**; yeni sohbet açılınca veri tazelenir.
- **Çözüldü (v2):** HITL onay kartları `session_id` ile kalıcı; sohbet geçmişi kullanıcı bazlı,
  sınırsız ve sahiplik korumalı (başka kullanıcı erişemez/silemez).
- **Çözüldü (v3):** Veri yaşam döngüsü (rollup+retention+sıkıştırma+artımlı) MSSQL şişmesini
  engeller; gerçek token logu; OpenAI kota hatasında zarif mesaj; `.env` önceliği.

---

## 15. Yol Haritası
**Tamamlandı:**
- ✅ Otomatik follow-up soru önerileri (her cevabın altında 3 takip sorusu)
- ✅ Çok-kiracılık + PDF-RAG (v2.0)
- ✅ **Semantic Layer** (metrik sözlüğü + admin Metrikler sayfası) (v3.0)
- ✅ **Canlı SAP sorgu + drill-down önbelleği + satıcı adı eşleme** (v3.0)
- ✅ **Veri yaşam döngüsü** (rollup + retention + sıkıştırma + artımlı çekme) (v3.0)
- ✅ Gerçek token logu + kota dayanıklılığı + `.env` önceliği (v3.0)

**Sırada (Sprint 5+):**
- Daily Brief (sabah e-posta özeti) + zamanlanmış rapor aboneliği ("her Pazartesi maille")
- Multi-model routing (soru tipine göre GPT/Gemini/Claude)
- Belge yönetimi: klasör/etiket, sürüm, OCR (taranmış PDF)
- Canlı sorguda RAG'ı atlayan hızlı drill-down (önbellekteki takiplerde gecikmeyi azalt)
- Gerçek JWT/RBAC + parola hash + sır yönetimi (güvenlik sertleştirme)

---

## 16. Sözlük (SAP Alanları)
| Alan | Anlam |
|------|-------|
| `TKNUM` | Sevkiyat numarası |
| `VBELN` | Teslimat belgesi |
| `ERDAT` | Oluşturma tarihi |
| `MUSTERI_ADI` | Müşteri adı |
| `CITY1` | Şehir |
| `LFIMG` | Teslim miktarı |
| `TDURUM` / `TDURUM_TNM` | Transfer durumu (kod / metin) |
| `VSART` / `VSART_TNM` | Sevkiyat türü |
| `ROUTE` / `ROUTE_TNM` | Rota |
| `MATNR` / `MAKTX` | Malzeme no / adı |

### SAS Servisi (satınalma — canlı sorgu) alanları
| Alan | Anlam |
|------|-------|
| `FISCPER` | Mali yıl/dönem (7 hane YYYYPPP, örn. `2023001`) |
| `MATERIAL` | Malzeme (kod) |
| `PLANT` | Üretim yeri |
| `VENDOR` | Satıcı kodu (kullanıcıya `SATICI_ADI` olarak gösterilir) |
| `SATICI_ADI` | Satıcı adı (ET_RETURN_VENDOR'dan eşlenir — kullanıcıya bununla bahsedilir) |
| `AMOUNT` / `PRICE` / `PRICE_UNIT` | Tutar / birim fiyat / fiyat birimi |
| `CURRENCY` | Para birimi (örn. TRY) |
| `__BIC__ZTERM` | Ödeme koşulu (gün) |
