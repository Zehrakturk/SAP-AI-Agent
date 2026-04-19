# SAP-AI-Agent

# Bitirme Projesi Haftalık İlerleme Raporu

## Proje Bilgileri

| Alan | Bilgi |
|------|-------|
| **Öğrenci Adı Soyadı** | *(Zehra Aktürk)* |
| **Öğrenci No** | *(21360859049)* |
| **Proje Başlığı** | *(Kurumsal Yapay Zeka Ajanı)* |
| **Danışman** | Prof. Dr. Turgay Tugay Bilgin |
| **Dönem** | 2025-2026 Bahar |

---

## İş Planı


| Hafta | Tarih Aralığı | Planlanan İş | Tahmini Tamamlanma (%) | Durum |
|-------|---------------|--------------|------------------------|-------|
| 1 | 30.03 - 05.04 | *Literatür taraması yapmak ve bir yol haritası çıkarmak* | %5 | ✅ Tamamlandı |
| 2 | 06.04 - 13.04 | *SAP’den veri çekme (ABAP API / batch job) ve JSON formatına dönüştürme* | %10  | ✅ Tamamlandı |
| 3 | 13.04 - 19.04 | *Verilerin temizlenmesi ve AI için uygun hale getirilmesi (preprocessing)*| %25 | 🔄 Devam Ediyor |
| 4 | 19.04 - 26.04 | *Temel kullanıcı arayüzü (chat ekranı) oluşturma*| %35 | ⬜ Başlamadı |
| 5 | 27.04 - 03.05 | *Vector database kurulumu ve embedding işlemleri (RAG altyapısı)* | %45 | ⬜ Başlamadı |
| 6 | 04.05 - 10.05 | *Otomatik veri besleme pipeline’ı (scheduler: günlük veri aktarımı)* | %60 | ⬜ Başlamadı |
| 7 | 11.05 - 17.05 | *AI’nin kendi veritabanından sorgu yapması ve doğru cevap üretmesi (retrieval + reasoning)* | %70 | ⬜ Başlamadı |
| 8 | 18.05 - 24.05 | *İş kuralları (business logic): karlılık, risk analizi, öneri üretimi* | %80 | ⬜ Başlamadı |
| 9 | 01.06 - 07.06 | *Testler (veri doğruluğu + AI cevap kalitesi) ve bug fix* | %90 | ⬜ Başlamadı |
| 10 | 08.06 - 14.06 | *Yorum doğruluk oranı optimizasyonu* | %100 | ⬜ Başlamadı |

**Durum simgeleri:** ⬜ Başlamadı | 🔄 Devam Ediyor | ✅ Tamamlandı | ⚠️ Gecikti

---

## Haftalık İlerleme Kayıtları

---### Hafta 3 *(Tarih: 13.04.2026 - 19.04.2026)*

**Plandaki hedef:**
- Verilerin temizlenmesi ve AI için uygun hale getirilmesi (preprocessing)*

**Bu hafta yaptıklarım:**
- SAP kaynaklı veriler ve tablo yapıları modele tanıtıldı. Kullanıcı girdilerini otomatik sorguya dönüştüren mimari geliştirildi.

**Plana göre durumum:**
- Proje planına tam uyum sağlanmakla birlikte, ilgili süreçler takvime uygun olarak devam etmektedir.

**Karşılaştığım sorunlar / zorluklar:**
- Kullanıcı tarafından iletilen serbest metin halindeki taleplerin, hatasız ve optimize edilmiş veritabanı sorgularına dönüştürülmesinde 'belirsizlik' (ambiguity) sorunları yaşanmıştır.

**Gelecek hafta hedefim:**
- Kullanıcıdan gelen taleplerin modele aktarılacağı ve model yanıtlarının görselleştirileceği chat ekranı arayüz tasarımının gerçekleştirilmesi.

### Hafta 2 *(Tarih: 06.04.2026 - 12.04.2026)*

**Plandaki hedef:**
- SAP’den veri çekme (ABAP API / batch job) ve JSON formatına dönüştürme

**Bu hafta yaptıklarım:**
- SAP den veri çekilebişdi. Kullanıı tabiki için örnek log sistemi kuruldu.

**Plana göre durumum:**
- Plana uyuldu.

**Karşılaştığım sorunlar / zorluklar:**
- Veri alırken lokalde çalışabiliyor olmak ve verilerin boyutunun fazla olması 

**Gelecek hafta hedefim:**
- Her sorguda veri çekmek mantıksız olacağı için hem de hafıza oluşturmak için alınan veriler bir veritabanına yazılacaktır.

### Hafta 1 *(Tarih: 30.03.2026 - 03.04.2026)*

**Plandaki hedef:**
- *Literatür taraması yapmak ve bir yol haritası çıkarmak*

**Bu hafta yaptıklarım:**
- *SAP dünyasında Joule olmadan yapay zeka entegrasyonları nasıl planlandığı ve entegre edildiği incelendi.*

**Plana göre durumum:**
- *Literatür araştırmasında Odata, RFC servisler ve excel aracılığı ile SAP den verinin alınabildiğini gördüm. Proje planına uyup litertürü taradım.*

**Karşılaştığım sorunlar / zorluklar:**
- *Yok*

**Gelecek hafta hedefim:**
- *Veri entegrasyonu sağlamak ve ve model eğitimine başlamak*

---

<!--
ŞABLON: Yeni hafta eklemek için aşağıdaki bloğu kopyalayıp üste yapıştırın.

### Hafta X *(Tarih: GG.AA.YYYY - GG.AA.YYYY)*

**Plandaki hedef:**
- 

**Bu hafta yaptıklarım:**
- 

**Plana göre durumum:**
- 

**Karşılaştığım sorunlar / zorluklar:**
- 

**Gelecek hafta hedefim:**
- 

---
-->
