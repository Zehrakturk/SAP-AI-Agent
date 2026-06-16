# -*- coding: utf-8 -*-
"""
testdata/seed_demo_docs.py — DEMO PDF bilgi tabanı (PDF-RAG) için SENTETİK kılavuzlar.

Tezde "bilgi / nasıl-yapılır" sorularının ekran görüntüsü için, kurumun gerçek
belgeleri yerine tamamen UYDURMA 3 kılavuz üretir, 'Demo' firmasına indeksler.

- reportlab varsa: gerçek PDF dosyaları üretir (data/demo_docs/) ve normal PDF
  hattından (doc_rag.index_pdf) indeksler.
- reportlab yoksa: metni doğrudan doc-RAG'a indeksler (PDF üretmeden).

Çalıştır:  cd SAP-AI ;  python testdata/seed_demo_docs.py --yes
(--yes gerekli, çünkü OpenAI embedding çağrısı = maliyet.)
Sonra "demo / demo123" ile giriş yapıp bilgi sorularını sorabilirsiniz.
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv(override=True)

COMPANY  = "Demo"
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_docs")

# ───────────────────────── sahte kılavuz içerikleri (UYDURMA) ─────────────────────────
MANUALS = [
    ("SAP-AI Copilot Kullanim Kilavuzu.pdf", "SAP-AI Copilot Kullanım Kılavuzu", """\
Bu kılavuz, SAP-AI Copilot uygulamasının temel kullanımını açıklar. Bu belge demo
amaçlıdır ve gerçek kurumsal bilgi içermez.

Giriş yapma
Uygulamaya kullanıcı adı ve parola ile giriş yapılır. Demo ortamında "demo" kullanıcı
adı ve "demo123" parolası kullanılır. Giriş yapıldığında kullanıcı yalnızca kendi
firmasının verilerini görür.

Soru sorma
Sohbet ekranına sorunuzu günlük dilde yazmanız yeterlidir. Sistem sorunuzu çözümleyerek
uygun veriye erişir ve yanıtı doğal dilde üretir. Teknik bilgi, SQL veya tablo adı
bilmeniz gerekmez.

Çıktı biçimleri
Sistem varsayılan olarak kısa ve net bir metin yanıtı verir. "Listele" veya "tablo"
derseniz sonuç tablo biçiminde gösterilir. "Rapor", "grafik" ya da "görsel" derseniz
grafik ve temel göstergelerden oluşan tam bir görselleştirme üretilir.

Takip soruları
Her yanıtın altında önerilen takip soruları görünür. Bu önerilere tıklayarak aynı
konuda ayrıntıya inebilirsiniz.

Belgeler sayfası
Bilgi ve "nasıl yapılır" türü sorular, Belgeler sayfasından yüklenen PDF kılavuzlardan
yanıtlanır. Yeni bir kılavuz yüklemek için Belgeler sayfasını kullanın; yüklenen belge
yalnızca kendi firmanız için erişilebilir olur.
"""),

    ("Sevkiyat Surecleri El Kitabi.pdf", "Sevkiyat Süreçleri El Kitabı", """\
Bu el kitabı, sevkiyat verilerinin alanlarını ve süreç kurallarını açıklar. İçerik
demo amaçlı olup uydurmadır.

Sevkiyat durum kodları
Her sevkiyatın bir durum kodu vardır:
- 01: OLUŞTURULDU — sevkiyat kaydı açılmıştır.
- 02: MAL ÇIKIŞI YAPILDI — ürün depodan çıkmıştır.
- 03: YOLDA — sevkiyat taşınmaktadır.
- 04: TESLİM EDİLDİ — ürün müşteriye ulaşmıştır.

Gecikme tanımı
Bir sevkiyat, istenilen teslimat tarihi geçtiği hâlde durumu TESLİM EDİLDİ değilse
gecikmiş kabul edilir. Gecikme analizlerinde istenilen teslimat tarihi ile fiili
teslimat tarihi karşılaştırılır.

Nakliye tipleri
Sevkiyatlar karayolu, denizyolu veya havayolu ile yapılabilir. Her sevkiyatta nakliye
tipi, rota, araç plakası ve sürücü bilgisi tutulur.

Hacim ve miktar
Teslim edilen miktar kalem bazında, hacim ise metreküp (M3) cinsinden saklanır. Bir
sevkiyat birden çok kalem içerebilir; bu nedenle sevkiyat sayısı hesaplanırken taşıma
numarası tekilleştirilir.
"""),

    ("Sik Karsilasilan Hatalar ve Cozumleri.pdf", "Sık Karşılaşılan Hatalar ve Çözümleri", """\
Bu belge, demo ortamında karşılaşılabilecek tipik durumları ve çözümlerini listeler.
İçerik uydurmadır.

"Veri bulunamadı" yanıtı
İlgili döneme ait veri henüz çekilmemiş olabilir. Sistem böyle durumlarda ilgili
entegrasyonun çalıştırılması için onay ister. Kullanıcı onayladıktan sonra yönetici
onayı verilince veri SAP'tan çekilir ve soru otomatik olarak yeniden çalıştırılır.

"Entegrasyon pasif" durumu
Bir entegrasyondan veri gelmiyorsa, yöneticinin Entegrasyonlar sayfasından ilgili
entegrasyonu etkin duruma getirmesi gerekir.

Yetki veya firma hatası
Kullanıcılar yalnızca kendi firmalarının verisine erişebilir. Beklenen veri
görünmüyorsa, doğru firma hesabıyla giriş yapıldığından emin olun.

Sayıların beklenenden farklı olması
Gecikme veya toplam miktar gibi iş terimlerinin hesabı metrik sözlüğünde tanımlıdır.
Bir göstergenin tanımı değiştirilmek istenirse metrik sözlüğü güncellenir.

"PDF'ten metin çıkarılamadı" hatası
Yüklenen PDF taranmış bir görüntü olabilir. Bu durumda belgenin metin tabanlı bir
sürümü yüklenmeli ya da OCR ile metne dönüştürülmelidir.
"""),

    ("Seyahat Talebi Olusturma Kilavuzu.pdf", "Seyahat Talebi Oluşturma Kılavuzu", """\
Bu kılavuz, kurumsal portal üzerinden seyahat (görevlendirme) talebinin nasıl
oluşturulduğunu açıklar. İçerik demo amaçlıdır ve uydurmadır.

Seyahat talebi nasıl açılır
1. Portalda "Self Servis > Seyahat ve Masraf > Yeni Seyahat Talebi" adımına gidin.
2. Seyahat türünü seçin: Yurt İçi veya Yurt Dışı.
3. Başlangıç ve bitiş tarihlerini, gidiş ve dönüş şehirlerini girin.
4. Seyahat nedenini (örneğin müşteri ziyareti, eğitim, fuar) ve ilgili maliyet
   yerini (cost center) belirtin.
5. Ulaşım (uçak, otobüs, şirket aracı) ve konaklama ihtiyacını işaretleyin.
6. Tahmini bütçeyi girin ve "Onaya Gönder" düğmesine basın.

Onay süreci
Seyahat talebi önce ilk amirin, ardından yurt dışı ise ilgili direktörün onayına
düşer. Onay durumunu "Taleplerim" ekranından izleyebilirsiniz. Talep reddedilirse
ret gerekçesi aynı ekranda görünür.

Avans ve bilet
Talep onaylandıktan sonra seyahat avansı talep edebilir, biletleme için anlaşmalı
seyahat acentesine otomatik bildirim gönderebilirsiniz. Bilet bilgileri talebe
otomatik olarak eklenir.

Seyahat sonrası
Seyahat bittikten sonra 15 gün içinde masraf beyanı oluşturulmalıdır. Avans alındıysa
masraf beyanı sırasında avans mahsuplaştırılır.
"""),

    ("IT Destek Talebi Acma Kilavuzu.pdf", "IT Destek Talebi (Ticket) Açma Kılavuzu", """\
Bu kılavuz, IT departmanına nasıl destek talebi (ticket) açılacağını anlatır. İçerik
demo amaçlı olup uydurmadır.

IT ticket nasıl açılır
1. "Hizmet Masası" (Service Desk) portalını açın.
2. "Yeni Talep Oluştur" düğmesine tıklayın.
3. Kategori seçin: Donanım, Yazılım, Ağ/İnternet, Erişim/Yetki veya Diğer.
4. Önceliği belirleyin: Düşük, Orta, Yüksek veya Kritik.
5. Konu ve açıklama alanını doldurun; mümkünse hata ekran görüntüsünü ekleyin.
6. "Gönder" dediğinizde size bir talep numarası (örneğin INC-100245) verilir.

Öncelik ve çözüm süreleri
- Kritik: hizmet tamamen durmuş, hedef yanıt 1 saat.
- Yüksek: iş ciddi etkileniyor, hedef yanıt 4 saat.
- Orta: kısmi etki, hedef yanıt 1 iş günü.
- Düşük: bilgi veya küçük talep, hedef yanıt 3 iş günü.

Talebi takip etme
Açtığınız talepleri "Taleplerim" sekmesinden izleyebilir, IT ekibinin sorularına
yorum ekleyerek yanıt verebilirsiniz. Talep çözüldüğünde size bildirim gelir ve
çözümü onaylamanız istenir.

Sık açılan talep türleri
Parola sıfırlama, yeni yazılım kurulumu, paylaşılan klasör erişimi, yazıcı tanımlama
ve VPN erişimi en sık açılan taleplerdir. Parola sıfırlama talepleri çoğunlukla
otomatik olarak karşılanır.
"""),

    ("Izin Talebi Sureci.pdf", "İzin Talebi Süreci", """\
Bu belge, yıllık izin ve diğer izin türlerinin talep sürecini açıklar. İçerik demo
amaçlıdır ve uydurmadır.

İzin talebi nasıl oluşturulur
1. "Self Servis > İzin İşlemleri > Yeni İzin Talebi" adımına gidin.
2. İzin türünü seçin: Yıllık İzin, Mazeret İzni, Ücretsiz İzin veya Raporlu.
3. Başlangıç ve bitiş tarihlerini seçin; sistem iş günü sayısını otomatik hesaplar.
4. Yerinize bakacak kişiyi (vekil) belirtin ve talebi onaya gönderin.

Onay ve bakiye
İzin talebi ilk amirin onayına düşer. Onaylanan izin, yıllık izin bakiyenizden düşülür.
Kalan izin bakiyenizi "İzin Bakiyem" ekranından görebilirsiniz. Gelecek yıla devreden
izinler ilgili yılın sonuna kadar kullanılmalıdır.

İptal ve değişiklik
Başlamamış bir izni "Taleplerim" ekranından iptal edebilirsiniz; iptal de amir onayına
düşer. Başlamış izinlerde değişiklik için İnsan Kaynakları ile iletişime geçilmelidir.
"""),

    ("Masraf Beyani ve Onayi.pdf", "Masraf Beyanı ve Onayı", """\
Bu kılavuz, seyahat veya iş giderlerinin masraf beyanı ile nasıl bildirileceğini
açıklar. İçerik demo amaçlı olup uydurmadır.

Masraf beyanı nasıl oluşturulur
1. "Self Servis > Seyahat ve Masraf > Yeni Masraf Beyanı" adımına gidin.
2. Varsa ilgili seyahat talebini seçin; masraf otomatik olarak ona bağlanır.
3. Her gider için tür (konaklama, ulaşım, yemek, yakıt vb.), tutar, para birimi ve
   tarih girin.
4. Fatura veya fişin fotoğrafını/PDF'ini ilgili satıra ekleyin.
5. Toplam tutarı kontrol edip "Onaya Gönder" deyin.

Belge zorunluluğu
Tutarı belirlenen limitin üzerindeki her gider için fatura veya fiş eklenmesi
zorunludur. Belgesiz giderler onaylayan tarafından reddedilebilir.

Onay ve ödeme
Masraf beyanı önce amir, ardından Finans onayından geçer. Onaylanan tutar bir sonraki
maaş ödemesiyle veya ayrı bir ödeme olarak hesabınıza aktarılır. Avans alınmışsa avans
mahsuplaştırılır ve yalnızca fark ödenir.
"""),

    ("Satinalma Talebi Olusturma.pdf", "Satınalma Talebi (PR) Oluşturma", """\
Bu belge, malzeme veya hizmet için satınalma talebi (purchase requisition) açma
sürecini anlatır. İçerik demo amaçlıdır ve uydurmadır.

Satınalma talebi nasıl açılır
1. "Satınalma > Yeni Talep" ekranını açın.
2. Talep türünü seçin: Stok Malzemesi, Stok Dışı Malzeme veya Hizmet.
3. Malzeme kodunu veya hizmet açıklamasını, miktarı ve ihtiyaç tarihini girin.
4. Maliyet yeri (cost center) ve teslim yerini belirtin.
5. Talebi onaya gönderin; sistem size bir talep numarası verir.

Onay ve sipariş
Talep, tutara göre kademeli onaydan geçer. Onaylanan talep satınalma ekibine düşer ve
uygun tedarikçiye sipariş (purchase order) olarak dönüştürülür. Talebinizin hangi
aşamada olduğunu "Taleplerim" ekranından izleyebilirsiniz.

İpuçları
Aynı malzeme için tekrarlı talep açmak yerine miktarı tek talepte toplayın. Acil
ihtiyaçlarda öncelik alanını "Yüksek" seçin ve açıklama alanına gerekçe yazın.
"""),
]

EXAMPLES = [
    "Seyahat talebi nasıl açılır?",
    "IT'ye nasıl ticket açarım?",
    "Yıllık izin talebini nasıl oluştururum?",
    "Masraf beyanı nasıl yapılır?",
    "Satınalma talebi nasıl açılır?",
    "Sevkiyat durum kodları nelerdir?",
]


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _make_pdf(title: str, body: str) -> bytes | None:
    """reportlab + DejaVu (Türkçe) ile PDF baytı üretir; başarısızsa None."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import matplotlib.font_manager as fm

        font_path = fm.findfont("DejaVu Sans")
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        h = ParagraphStyle("H", fontName="DejaVu", fontSize=16, leading=20, spaceAfter=14)
        b = ParagraphStyle("B", fontName="DejaVu", fontSize=11, leading=16, spaceAfter=8)
        flow = [Paragraph(_xml_escape(title), h), Spacer(1, 6)]
        for para in body.split("\n\n"):
            flow.append(Paragraph(_xml_escape(para).replace("\n", "<br/>"), b))
        doc.build(flow)
        return buf.getvalue()
    except Exception as e:
        print(f"   (reportlab ile PDF üretilemedi, metin indekslemeye düşülüyor: {e})")
        return None


def _index_text_direct(text: str, filename: str, company: str):
    """reportlab yoksa: metni doğrudan doc-RAG'a indeksler (index_pdf mantığını taklit)."""
    from app.services import doc_rag as dr
    from app.services.db import get_connection
    from qdrant_client.models import PointStruct

    chunks = dr._chunk(text)
    dr._ensure_collection()
    conn = get_connection(); cur = conn.cursor()
    try:
        dr._ensure_table(cur)
        cur.execute("""INSERT INTO documents
            (company, filename, title, page_count, char_count, chunk_count, uploaded_by)
            OUTPUT INSERTED.id VALUES (?,?,?,?,?,?,?)""",
            (company, filename[:300], filename[:300], 1, len(text), len(chunks), "demo"))
        doc_id = int(cur.fetchone()[0]); conn.commit()
    finally:
        conn.close()
    points = [PointStruct(id=str(uuid.uuid4()), vector=dr._embed(ch),
                          payload={"document_id": doc_id, "company": company,
                                   "filename": filename, "chunk_index": i, "text": ch[:2000]})
              for i, ch in enumerate(chunks)]
    dr._qdrant.upsert(collection_name=dr.DOC_COLLECTION, points=points)
    return {"status": "ok", "document_id": doc_id, "chunks": len(chunks)}


def _cleanup_demo_docs():
    """Önceki demo belgelerini sil (idempotent) — yalnız 'Demo' firması."""
    from app.services import doc_rag as dr
    from app.services.db import get_connection
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    conn = get_connection(); cur = conn.cursor()
    try:
        dr._ensure_table(cur)
        cur.execute("DELETE FROM documents WHERE company = ?", (COMPANY,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
    try:
        dr._ensure_collection()
        dr._qdrant.delete(collection_name=dr.DOC_COLLECTION,
                          points_selector=Filter(must=[FieldCondition(
                              key="company", match=MatchValue(value=COMPANY))]))
    except Exception as e:
        print(f"   (Qdrant temizleme uyarısı: {e})")


def main():
    if "--yes" not in sys.argv:
        print("Bu script 'Demo' firması için sahte PDF kılavuzları indeksler (OpenAI embedding = maliyet).")
        print(f"  Hedef DB_NAME = {os.getenv('DB_NAME')!r} | Qdrant DOCS koleksiyonu")
        print("  Devam için:  python testdata/seed_demo_docs.py --yes")
        return

    os.makedirs(DOCS_DIR, exist_ok=True)
    print("[1/2] Önceki demo belgeleri temizleniyor...")
    _cleanup_demo_docs()

    print("[2/2] Sahte kılavuzlar üretiliyor ve indeksleniyor...")
    from app.services.doc_rag import index_pdf
    for filename, title, body in MANUALS:
        pdf = _make_pdf(title, body)
        if pdf:
            path = os.path.join(DOCS_DIR, filename)
            with open(path, "wb") as f:
                f.write(pdf)
            res = index_pdf(pdf, filename, COMPANY, uploaded_by="demo")
            print(f"   ✓ {filename}  → {res.get('chunks','?')} chunk (PDF: {path})")
        else:
            res = _index_text_direct(body, filename, COMPANY)
            print(f"   ✓ {filename}  → {res.get('chunks','?')} chunk (metin indeksleme)")

    print("\n✓ Demo bilgi tabanı hazır. 'demo / demo123' ile giriş yapıp sorabilirsiniz:")
    for q in EXAMPLES:
        print(f"   - {q}")


if __name__ == "__main__":
    main()
