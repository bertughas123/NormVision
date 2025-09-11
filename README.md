# NormVision – Dynamic Visit & Sales Intelligence Platform

Kurumsal ziyaret raporlarını, satış ve finans verilerini tek akışta işleyip birleşik içgörülere dönüştüren modüler analiz ve raporlama platformu.

---
## 🚀 Amaç
NormVision; PDF ziyaret özetlerinden, satış Excel raporlarından ve finansal tablolardan gelen verileri:
- Yapılandırır (extract & normalize)
- Zenginleştirir (LLM destekli alan doldurma + yorumlama)
- KPI & performans analizlerine dönüştürür
- Kampanya – satış ilgisi kesişimini çıkarır
- Tek konsolide Final Rapor üretir (JSON + Markdown)

---
## 🧱 Mimari Katmanlar
| Katman | Modüller | Sorumluluk |
|--------|----------|------------|
| Extraction | `extractor/` (pdf_reader, sections, normalize, llm_fill, campaigns, notlar_parser) | PDF + içerik ayrıştırma, LLM ile alan tamamlama |
| Analysis | `analyzer/` (sales_performance, financial_analysis) | Satış kırılımı ve finansal metrik üretimi |
| KPI Builder | `runners/runner_monthly.py` | Ziyaret bazlı KPI + kampanya JSON & MD üretimi |
| Bridge | `bridge/sales_visit_bridge.py` | Ürün ilgisi – kampanya eşleşmesine hazırlık |
| Final Assembly | `bridge/final_assembler.py` | Satış+Finans + KPI + Bridge analizini konsolide etme |
| Orkestrasyon | `pipeline_workflow.py` | Uçtan uca aylık pipeline (4 adım) |
| Utilities | `utils/company_name_utils.py` | Şirket adı kanonik normalizasyonu |

---
## 🔄 Veri Akışı (Tek Kaynak Prensibi)
1. `sales_performance.py` → `datasforfinalblock/LLM_Input_Satis_Analizi.json` (temel satış + malzeme analizi)
2. `financial_analysis.py` → Aynı dosyayı açar ve finansal blokları ekler (üzerine yazmaz, zenginleştirir)
3. `runner_monthly.py` → `Reports/Monthly/{COMPANY}/{MM-Ay}/NormVision_KPI_*.json` + `.md`
4. `final_assembler.py` → Satış+Finans JSON + ilgili KPI JSON’u bulur, ürün ilgisi ↔ kampanya kesişimi (Bridge), final birleşik rapor JSON'u oluşturur.

---
## 📁 Standart Klasör Yapısı
```
datasforfinalblock/
   LLM_Input_Satis_Analizi.json           # Zenginleştirilmiş satış + finans
   SIRINLER_BAGLANTI_ELEM.-BOYA/
      Final_Report_YYYYMMDD_HHMMSS.json    # Final rapor(lar)
   *.xlsx                                 # Kaynak veri Excel’leri

Reports/Monthly/
   SIRINLER_BAGLANTI_ELEM.BOYA/
      07-Temmuz/
         NormVision_KPI_*.json
         NormVision_Aylik_Rapor_*.md
```
ENV ile konumlar:
```
REPORTS_BASE=...\NormHoldingDynamicSummarizer\Reports\Monthly
DATAS_BASE=...\datasforfinalblock
```

---
## 🔤 Şirket Adı Normalizasyonu
`utils/company_name_utils.py`:
- Türkçe karakter → ASCII (Ş→S, Ö→O, Ğ→G, Ü→U, Ç→C, ı→i)
- NFKD + diakritik temizleme
- Klasör için: Nokta (.) ve tire (-) korunur, boşluk → `_`
- Dosya için (isteğe bağlı varyant): `.` ve `-` da `_`
- Fazla ayıraçlar daraltılır, uzunluk sınırı uygulanır

Örnekler:
| Orijinal | Klasör | Dosya-uyumlu |
|----------|--------|-------------|
| `ŞİRİNLER BAĞLANTI ELEM.-BOYA` | `SIRINLER_BAGLANTI_ELEM.-BOYA` | `SIRINLER_BAGLANTI_ELEM_BOYA` |

---
## 🧪 Pipeline Aşamaları
| Adım | Script | Çıktı | Kritik Noktalar |
|------|--------|-------|-----------------|
| 1 | `runner_monthly.py` | KPI JSON + Markdown | PDF çözümleme, kampanya listesi |
| 2 | `analyzer/sales_performance.py` | Satış+malzeme analizi JSON & Excel | Malzeme bazlı grupla |
| 3 | `analyzer/financial_analysis.py` | JSON enrich | Ortalama tahsilat, risk, limit uyumu |
| 4 | `bridge/final_assembler.py` | Final birleşik rapor | Şirket adı + ay bazlı eşleşme |

`pipeline_workflow.py` hepsini orkestre eder (subprocess, UTF-8 ortam, zaman ölçümü, sonuç tablosu).

---
## 🔐 Encoding ve Platform Dayanıklılığı
- Windows `charmap` hatalarına karşı tüm subprocess çağrılarında `PYTHONIOENCODING=utf-8`
- Dosya yazımı: `encoding='utf-8'`
- JSON çıktıları: `ensure_ascii=False`
- Problemli emoji / non-BMP karakterler kaldırıldı

---
## 📊 Finansal Metrikler (Örnek)
| Alan | Açıklama |
|------|---------|
| `payment_compliance_rate` | Vade uyumu (%) |
| `avg_collection_period` | Tahsilat gün ortalaması |
| `credit_limit_compliance` | Limit aşımı durumu |
| `risk_assessment` | Basit segment yorumu |
| `recommendations` | Ödeme/limit önerileri |

---
## 🔍 Bridge Analizi (Ürün Kesişimi)
Kaynaklar:
- `malzeme_analizi` → İlgilenilen / sipariş edilen ürün grupları
- `sunulan_urunler_ve_kampanyalar` → Kampanya ürünleri

Çıktı örneği:
```
"bridge_analizi": {
   "ilgilenilen_urun_gruplari": [...],
   "sunulan_urun_gruplari": [...],
   "teklif_verilen_urun_gruplari": [...],
   "analiz_tarihi": "YYYY-MM-DD HH:MM:SS",
   "analiz_durumu": "Başarılı|Başarısız"
}
```

---
## 🛡️ Git Ignore Stratejisi
Repository’de tutulmayanlar:
- `Reports/`
- `datasforfinalblock/`
- `crmyapayzekamodlrnekdataset/`
- Final raporlar (`Final_Report_*.json`)
- Hassas dokümantasyon (`COMPANY_FILE_STRUCTURE.md`, `README_New_Architecture.md`)
- Batch log ve geçici pipeline dosyaları

---
## ⚙️ Kurulum
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# .env içine API anahtarlarını ve base path'leri gir
```

Minimum `.env`:
```
GEMINI_API_KEY=YOUR_KEY
REPORTS_BASE=...\\NormHoldingDynamicSummarizer\\Reports\\Monthly
DATAS_BASE=...\\datasforfinalblock
```

---
## ▶️ Çalıştırma
### Tek Aylık Pipeline (Önerilen)
```powershell
python pipeline_workflow.py --month 7 --year 2025
```
### Manuel Adımlar
```powershell
python runners/runner_monthly.py --month 7 --year 2025 --input-dir "crmyapayzekamodlrnekdataset/pdfs" --llm
python -m analyzer.sales_performance
python -m analyzer.financial_analysis
python -m bridge.final_assembler --month 7
```

---
## 🧪 Roadmap (Seçili)
| Başlık | Durum | Not |
|--------|-------|-----|
| Fuzzy KPI klasör eşleşmesi | Plan | Levenshtein / rapidfuzz |
| Çoklu müşteri batch pipeline | Plan | Company list ingestion |
| Markdown → HTML/Email | Plan | Jinja2 templating |
| Zamanlanmış otomasyon | Plan | Task Scheduler / cron |
| Web dashboard | Plan | FastAPI + Vue/React |
| Lokal LLM fallback | Plan | Embedding veya rule-based |

---
## ❗ Sorun Giderme
| Belirti | Çözüm |
|---------|-------|
| KPI klasörü bulunamadı | `normalize_company_name()` çıktısını logla, folder ile kıyasla |
| Unicode `charmap` hatası | Ortama `PYTHONUTF8=1` ekleyin, UTF-8 print kullanın |
| JSON’da `\u0131` kaçışları | `ensure_ascii=False` ile yeniden yazın |
| Bridge boş dönüyor | KPI kampanya listesi veya malzeme_analizi eksik |

---
## 📌 Örnek Final Rapor (Kırpılmış)
```json
{
   "musteri_adi": "ŞİRİNLER BAĞLANTI ELEM.-BOYA",
   "malzeme_analizi": {"...": "..."},
   "finansal_analiz": {
      "odeme_uyum_orani": "94.67%",
      "ortalama_tahsilat_suresi": "73.55 gün",
      "kredi_limit_uyumu": "EVET"
   },
   "kpi_analizi": {"toplam_ziyaret": 6},
   "bridge_analizi": {"analiz_durumu": "Başarılı"},
   "final_report_metadata": {"rapor_versiyonu": "1.0"}
}
```

---
## 🔒 Lisans
Kurumsal / Proprietary – Norm Holding iç kullanım için.

---
## 👤 İletişim
İç geliştirme ekibi: Bilgi Teknolojileri / Veri & Analitik Birimi.

---
> Bu doküman otomatik güncellenmeye uygundur; mimari değişikliklerinde lütfen senkron tutun.
