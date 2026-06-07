# PRD — SAP-AI Copilot
**Ürün:** SAP + AI Tabanlı Karar Destek & Veri Entegrasyon Platformu
**Sürüm:** 2.0 · **Tarih:** 2026-06 · **Durum:** Aktif geliştirme (Sprint 1–3 + Human-in-the-loop + Çok-Kiracılık + PDF-RAG tamamlandı)

> **v2.0 yenilikleri:** Çok-kiracılık (Warmhaus / Beyçelik firma ayrımı), girişte firma seçici,
> PDF-RAG belge bilgi tabanı (**Belgeler** sayfası), rapor↔bilgi soru yönlendirme, her cevabın
> altında akıllı takip soruları, görünür **Çıkış Yap** butonu, Gemini `gemini-3.1-flash-lite`.

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
- Sohbet etiketleme + arama + sabitleme
- Görünür **Çıkış Yap** butonu → tam sayfa yenilemeden login ekranına dönüş (firma değiştirme)

**Hariç (şu an kapsam dışı):**
- Gerçek JWT/SSO kimlik doğrulama, satır-seviyesi RBAC (demo token kullanılıyor)
- Çoklu-dil arayüz, mobil uygulama
- Taranmış (image-only) PDF'lerde OCR (yalnız metin-tabanlı PDF desteklenir)
- Semantic Layer / metrik sözlüğü (Sprint 4)
- Zamanlanmış rapor aboneliği, Daily Brief (Sprint 4)

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
Model ayarları (in-memory), kullanıcı listesi, AI log akışı, kullanım metrikleri
(kısmen demo verisi).

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
│   │   ├── query.py             # /query/ask — sohbet sorgusu girişi (firma + yönlendirme)
│   │   ├── integrations.py      # entegrasyon CRUD + şablonlar + indeksleme (firma filtreli)
│   │   ├── documents.py         # PDF yükle/listele/sil + /documents/ask (PDF-RAG)
│   │   ├── insights.py          # proaktif içgörü + kişiselleştirme
│   │   ├── reports.py           # PDF/HTML export + e-posta
│   │   ├── enhance.py           # Gemini zenginleştirme uçları
│   │   └── approvals.py         # Human-in-the-loop onay API'si
│   ├── services/
│   │   ├── db.py                # merkezi MSSQL bağlantısı (get_connection)
│   │   ├── tenant.py            # çok-kiracılık: token'dan firma/rol/kullanıcı çıkarımı
│   │   ├── query_engine.py      # RAG + intent + SQL üretim + analiz + yönlendirme (çekirdek)
│   │   ├── doc_rag.py           # PDF-RAG: index_pdf / answer_question / classify_intent
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
├── data/
│   └── migrate_company.py       # tek seferlik: integrations.company kolonu + seed
├── static/                      # Vanilla JS frontend (sayfa başına modül)
│   ├── chats.js insights.js integrations.js reports.js dashboard.js documents.js
│   └── auth.js settings.js users.js logs.js charts.js tables.js api_client.js app.js
├── .env / .env.example          # sırlar (yalnız .env; .gitignore'da) + şablon
└── templates/index.html         # SPA kabuk
```

---

## 7. Veri Modeli (MSSQL — kod tarafından idempotent oluşturulur)
| Tablo | Amaç |
|-------|------|
| `shipments` | SAP sevkiyat verisi (TKNUM, ERDAT, MUSTERI_ADI, CITY1, LFIMG, TDURUM …) — Warmhaus |
| `integrations` | Entegrasyon tanımları (tip, url, auth, kimlik, **`company`** firma sahipliği) |
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

## 8. API Referansı (prefix `/api/v1`, ~80 route)
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

### 9.4 E-posta (rapor paylaşımı — opsiyonel, henüz .env'de yok)
`SMTP_HOST`, `SMTP_PORT` (vars. 587), `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_TLS` (vars. 1).
Ayarlanmazsa `/reports/email` 503 döner.

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
  ⚠️ `.env` daha önce commit'lendiyse git geçmişinden temizlenmeli ve anahtarlar **rotate** edilmeli.
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
| 02:00 | Tüm aktif entegrasyonlardan veri çek (`fetch_all_active`) |
| 03:00 | Proaktif içgörü üret (`generate_insights`) |
| Her 5 sn | HITL ingestion worker (`process_pending_jobs`) |

---

## 13. Kurulum & Çalıştırma
1. Şirket ağına bağlan (MSSQL `10.1.152.55` + Qdrant `10.30.10.1` erişimi gerekir).
2. `.env` dosyasını doldur (§9).
3. Bağımlılıklar: `Flask`, `flask-cors`, `apscheduler`, `openai`, `qdrant-client`, `zeep`,
   `pyodbc`, `python-dotenv`, `google-generativeai`, (opsiyonel PDF için) `weasyprint`.
4. `python run.py` → `http://localhost:3000` (giriş: `admin / admin123`).

---

## 14. Bilinen Sınırlamalar
- WeasyPrint kurulu değilse rapor PDF yerine HTML iner.
- E-posta `SMTP_*` ayarlanmadan çalışmaz (503 döner).
- Korelasyon içgörüsü için en az 2 entegrasyonda son 30 günde günlük veri gerekir.
- Taranmış (image-only) PDF'lerden metin çıkarılamaz (OCR yok) → "metin bulunamadı" uyarısı.
- Kimlik/RBAC demo seviyesinde (bkz. §11); firma izolasyonu token tabanlıdır.
- **Çözüldü (v2):** HITL onay kartları artık `session_id` ile oturuma bağlı kalıcı; sohbet
  geçmişi kullanıcı bazlı, sınırsız ve sahiplik korumalı tutulur (başka kullanıcı erişemez/silemez).

---

## 15. Yol Haritası (Sprint 4+)
- ✅ ~~Otomatik follow-up soru önerileri~~ (tamamlandı — her cevabın altında 3 takip sorusu)
- ✅ ~~Çok-kiracılık + PDF-RAG~~ (tamamlandı — v2.0)
- **Semantic Layer** (metrik sözlüğü — SQL doğruluğunu önemli ölçüde artırır)
- Daily Brief (sabah e-posta özeti)
- Zamanlanmış rapor aboneliği ("her Pazartesi maille")
- Multi-model routing (soru tipine göre GPT/Gemini/Claude)
- Belge yönetimi geliştirmeleri: klasör/etiket, sürüm, OCR (taranmış PDF)
- Gerçek JWT/RBAC + sır yönetimi (güvenlik sertleştirme)

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
