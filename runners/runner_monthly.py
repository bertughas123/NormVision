#!/usr/bin/env python3
"""
NormVision - Monthly Report Generator
Aylık ziyaret raporlarını analiz ederek kapsamlı aylık özet ve öneriler oluşturur.
"""

import sys
import argparse
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import google.generativeai as genai
import os
import time
from dotenv import load_dotenv

# Windows için UTF-8 fix
if sys.platform == "win32":
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

def safe_print(*args, **kwargs):
    """Güvenli print fonksiyonu - Unicode hatalarını engeller"""
    import unicodedata
    safe_args = []
    for arg in args:
        try:
            if isinstance(arg, str):
                # Unicode normalizasyonu
                normalized = unicodedata.normalize('NFKD', arg)
                # ASCII'ye dönüştür
                ascii_safe = normalized.encode('ascii', 'ignore').decode('ascii')
                safe_args.append(ascii_safe)
            else:
                # Non-string objeleri string'e çevir ve normalize et
                str_arg = str(arg)
                normalized = unicodedata.normalize('NFKD', str_arg)
                ascii_safe = normalized.encode('ascii', 'ignore').decode('ascii')
                safe_args.append(ascii_safe)
        except Exception:
            # En kötü durumda bile basit string representation kullan
            safe_args.append('[unprintable]')
    
    try:
        print(*safe_args, **kwargs)
    except UnicodeEncodeError:
        # Son çare: sadece ASCII printable karakterler
        ascii_args = []
        for arg in safe_args:
            ascii_args.append(''.join(c for c in str(arg) if ord(c) < 128))
        print(*ascii_args, **kwargs)

load_dotenv()

# Extractor modüllerini import et
sys.path.append(str(Path(__file__).parent.parent))
from extractor.pdf_reader import read_pdf_text
from extractor.sections import extract_notlar_block, extract_firma_adi
from utils.company_name_utils import normalize_company_name, normalize_for_filename
from extractor.notlar_parser import parse_notlar_kv, declared_keys
from extractor.llm_fill import llm_fill_and_summarize
from extractor.normalize import format_amount
from extractor.campaigns import check_campaign_mentions, get_current_campaigns

# .env dosyasını yükle (eğer load_dotenv fonksiyonu varsa)
try:
    load_dotenv()
except NameError:
    pass  # load_dotenv tanımlı değil, devam et

def process_single_pdf_for_monthly(pdf_path: str) -> Dict[str, Any]:
    """Tek bir PDF'yi aylık rapor için işler"""
    start_time = time.time()
    
    try:
        # PDF'yi oku
        text = read_pdf_text(pdf_path)
        
        # Firma adını çıkar
        firma_adi = extract_firma_adi(text)
        
        # Notlar bloğunu çıkar
        notlar = extract_notlar_block(text)
        
        # Regex ile parse et
        kv = parse_notlar_kv(notlar)
        
        # Declared keys'leri bul
        declared = declared_keys(notlar)
        
        # LLM ile eksik alanları doldur
        kv = llm_fill_and_summarize(kv, notlar, declared)
        
        def get_amt(prefix):
            return format_amount(kv.get(f"{prefix}_value"), kv.get(f"{prefix}_currency"), kv.get(f"{prefix}_raw"))
        
        # Ziyaret tarihini çıkar
        visit_date = extract_visit_date_from_filename(Path(pdf_path).name)
        
        elapsed_seconds = round(time.time() - start_time, 2)
        
        normalized_data = {
            'firma_adi': firma_adi or "—",
            'visit_date': visit_date,
            'ciro_2024': get_amt("ciro_2024"),
            'ciro_2025': get_amt("ciro_2025"),
            'q2_hedef': get_amt("q2_hedef"),
            'gorusulen_kisi': kv.get("gorusulen_kisi") or "—",
            'pozisyon': kv.get("pozisyon") or "—",
            'sunulan_urun_gruplari_kampanyalar': kv.get("sunulan_urun_gruplari_kampanyalar") or "—",
            'rakip_firma_sartlari': kv.get("rakip_firma_sartlari") or "—",
            'siparis_alindi_mi': kv.get("siparis_alindi_mi") or "—",
            'yaklasik_siparis_tutari': get_amt("yaklasik_siparis_tutari"),
            'genel_yorum': kv.get("genel_yorum") or "—",
            'ozet': kv.get("ozet") or "—"
        }
        
        return {
            'status': 'SUCCESS',
            'pdf_path': pdf_path,
            'pdf_name': Path(pdf_path).name,
            'data': normalized_data,
            'elapsed_seconds': elapsed_seconds,
            'processed_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        elapsed_seconds = round(time.time() - start_time, 2)
        safe_print(f"[ERROR] PDF isleme hatasi {pdf_path}: {str(e)}")
        return {
            'status': 'ERROR',
            'error_message': str(e),
            'pdf_path': pdf_path,
            'elapsed_seconds': elapsed_seconds,
            'processed_at': datetime.now().isoformat()
        }

def extract_visit_date_from_filename(filename: str) -> str:
    """Dosya adından ziyaret tarihini çıkarır"""
    # Örnek: Ziyaret Özeti (Norm)_20250617170617_TR.PDF
    pattern = r'_(\d{8})\d{6}_'
    match = re.search(pattern, filename)
    
    if match:
        date_str = match.group(1)  # YYYYMMDD
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            pass
    
    return "Tarih Bulunamadı"

def sanitize_company_name_for_filename(company_name: str) -> str:
    """
    Şirket adını dosya adı için güvenli hale getirir
    
    Args:
        company_name: Orijinal şirket adı
        
    Returns:
        str: Dosya adı için güvenli şirket adı
    """
    if not company_name or company_name.lower() in ['belirtilmemiş', '—', 'n/a']:
        return "UnknownCompany"
    
    # Türkçe karakterleri değiştir
    char_map = {
        'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
        'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'
    }
    
    sanitized = company_name
    for tr_char, en_char in char_map.items():
        sanitized = sanitized.replace(tr_char, en_char)
    
    # Dosya adı için güvenli olmayan karakterleri temizle
    sanitized = re.sub(r'[<>:"/\\|?*\s]+', '_', sanitized)
    
    # Birden fazla alt çizgiyi tek alt çizgiye dönüştür
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Başında ve sonunda alt çizgi varsa temizle
    sanitized = sanitized.strip('_')
    
    # Maksimum uzunluk sınırı (50 karakter)
    if len(sanitized) > 50:
        sanitized = sanitized[:50].rstrip('_')
    
    return sanitized or "UnknownCompany"

def filter_visits_by_month(visits: List[Dict], target_month: int, target_year: int) -> List[Dict]:
    """Belirtilen ay ve yıla ait ziyaretleri filtreler"""
    print(f"[DEBUG] Filtreleme başlıyor - Hedef: {target_month}/{target_year}")
    filtered = []
    for i, visit in enumerate(visits):
        print(f"[DEBUG] Ziyaret {i+1} - Status: {visit['status']}")
        if visit['status'] != 'SUCCESS':
            print(f"[DEBUG] Ziyaret {i+1} başarısız, atlanıyor")
            continue
            
        visit_date = visit['data'].get('visit_date', '')
        print(f"[DEBUG] Ziyaret {i+1} - Tarih: '{visit_date}'")
        if visit_date and visit_date != "Tarih Bulunamadı":
            try:
                date_obj = datetime.strptime(visit_date, '%Y-%m-%d')
                print(f"[DEBUG] Ziyaret {i+1} - Parse edildi: {date_obj.month}/{date_obj.year}")
                if date_obj.month == target_month and date_obj.year == target_year:
                    print(f"[DEBUG] Ziyaret {i+1} - EŞLEŞME BULUNDU!")
                    filtered.append(visit)
                else:
                    print(f"[DEBUG] Ziyaret {i+1} - Tarih eşleşmiyor")
            except ValueError as e:
                safe_print(f"[DEBUG] Ziyaret {i+1} - Tarih parse hatasi: {str(e)}")
                continue
        else:
            print(f"[DEBUG] Ziyaret {i+1} - Tarih bulunamadı veya geçersiz")
    
    print(f"[DEBUG] Filtreleme tamamlandı - {len(filtered)} eşleşme bulundu")
    return sorted(filtered, key=lambda x: x['data']['visit_date'])

def generate_monthly_analysis_with_llm(visits: List[Dict], month: int, year: int) -> tuple[str, str]:
    """LLM ile aylık analiz ve öneriler oluşturur (FIX SCRIPT'TEKİ ÇÖZÜMLERLE)
    
    Returns:
        tuple: (rapor_metni, json_ozet)
    """
    
    # API anahtarını kontrol et
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return "LLM analizi için GEMINI_API_KEY gerekli", "{}"
    
    try:
        genai.configure(api_key=api_key)
        # Fix script'te başarılı olan model kullan
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        
        # Veri özetini hazırla (fix script'teki gibi)
        month_names = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
            7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
        }
        
        # Ziyaret verilerini özetle ve istatistik hesapla
        visit_summaries = []
        siparis_sayisi = 0
        kampanya_listesi = []
        rakip_listesi = []
        
        for i, visit in enumerate(visits, 1):
            data = visit['data']
            date_str = data.get('visit_date', 'Belirtilmemiş')
            
            # Sipariş durumu kontrolü
            siparis_durumu = data.get('siparis_alindi_mi', '')
            if siparis_durumu and siparis_durumu.lower() not in ['hayır', '—', 'belirtilmemiş']:
                if 'evet' in siparis_durumu.lower() or 'alındı' in siparis_durumu.lower():
                    siparis_sayisi += 1
            
            # Kampanya bilgileri
            kampanya = data.get('sunulan_urun_gruplari_kampanyalar', '')
            if kampanya and kampanya != '—':
                kampanya_listesi.append(kampanya)
            
            # Rakip bilgileri
            rakip = data.get('rakip_firma_sartlari', '')
            if rakip and rakip != '—':
                rakip_listesi.append(rakip)
            
            visit_summaries.append(f"""
Ziyaret {i} ({date_str}):
- Ciro 2024: {data.get('ciro_2024', '—')}
- Ciro 2025: {data.get('ciro_2025', '—')}
- Kampanyalar: {kampanya if kampanya != '—' else 'Yok'}
- Sipariş: {siparis_durumu if siparis_durumu != '—' else 'Belirtilmemiş'}
- Detay: {data.get('genel_yorum', 'Detay yok')[:200]}...
""")
        
        # KISA VE ETKİLİ PROMPT (fix script'teki gibi)
        prompt = f"""Sen Norm Holding uzman satış analisti olarak {month_names[month]} {year} için KAPSAMLI analiz yap.

ZİYARET VERİLERİ:
{"\n\n".join(visit_summaries)}

TOPLAM İSTATİSTİKLER:
- Toplam ziyaret: {len(visits)}
- Sipariş alınan ziyaret: {siparis_sayisi}
- Başarı oranı: %{(siparis_sayisi/len(visits)*100):.1f}

LÜTFEN AŞAĞIDA BELİRTİLEN BAŞLIKLARDA DETAYLI ANALİZ YAP:

## AYLIK PERFORMANS ÖZETİ
- Ziyaret sıklığı ve müşteri önem seviyesi değerlendirmesi
- Ciro gelişimi analizi (2024-2025 karşılaştırma)
- Sipariş başarı oranı ve trendler

## KAMPANYA ETKİNLİĞİ ANALİZİ
- Sunulan kampanyaların analizi
- Hangi ürün grupları öne çıkıyor
- Kampanya kabul/red oranları

## RAKİP DURUM ANALİZİ
- Tespit edilen rakip firmalar ve şartları
- Rekabet gücümüz

## BAŞARILAR ve FIRSATLAR
- Hangi siparişler alındı?
- Kaçırılan fırsatlar neler?
- Gelecek ay için potansiyel?

## STRATEJİK ÖNERİLER
- Gelecek ay için aksiyon planı
- Odaklanılması gereken ürün grupları
- Müşteri ilişkisi geliştirme önerileri

**MUTLAKA SON KISIMDA ŞÖYLE BİR JSON ÖZET VER:**

```json
{{
    "ay": {month},
    "yil": {year},
    "toplam_ziyaret": {len(visits)},
    "siparis_sayisi": {siparis_sayisi},
    "basari_orani": {(siparis_sayisi/len(visits)*100):.1f},
    "sunulan_urunler_ve_kampanyalar": ["kampanya1", "kampanya2"],
    "tespit_edilen_rakipler": ["rakip1"],
    "onerililen_aksiyonlar": ["aksiyon1", "aksiyon2"],
    "genel_degerlendirme": "olumlu"
}}
```

ANALİZİ TÜRKÇE, DETAYLI VE PROFESYONEL ANALİZ YAP!"""

        print("[PROCESS] LLM ile gelişmiş analiz oluşturuluyor...")
        # Rate limiting için bekleme
        time.sleep(2)
        
        response = model.generate_content(prompt)
        full_response = response.text
        
        print(f"[DEBUG] LLM response length: {len(full_response)} characters")
        print(f"[DEBUG] Response contains 'json': {'json' in full_response.lower()}")
        
        # GELİŞMİŞ JSON PARSING (fix script'teki gibi)
        import re
        json_pattern = r'```json\s*(\{.*?\})\s*```'
        json_match = re.search(json_pattern, full_response, re.DOTALL)
        
        if json_match:
            json_ozet = json_match.group(1)
            print(f"[DEBUG] JSON found and extracted: {len(json_ozet)} characters")
            # JSON kısmını ana metinden çıkar
            rapor_metni = re.sub(json_pattern, '', full_response, flags=re.DOTALL).strip()
        else:
            print("[DEBUG] No JSON pattern found in response")
            # Alternatif JSON arama - sadece { } arasındaki son kısmı al
            lines = full_response.split('\n')
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip().startswith('{'):
                    in_json = True
                if in_json:
                    json_lines.append(line)
                if line.strip().endswith('}') and in_json:
                    break
            
            if json_lines:
                json_ozet = '\n'.join(json_lines)
                print(f"[DEBUG] Alternative JSON extraction: {len(json_ozet)} characters")
                rapor_metni = full_response
            else:
                # MANUEL JSON OLUŞTUR (fix script'teki gibi)
                json_ozet = f"""{{
    "ay": {month},
    "yil": {year},
    "toplam_ziyaret": {len(visits)},
    "siparis_sayisi": {siparis_sayisi},
    "basari_orani": {(siparis_sayisi/len(visits)*100):.1f},
    "sunulan_urunler_ve_kampanyalar": {str(kampanya_listesi[:3])},
    "tespit_edilen_rakipler": {str(rakip_listesi[:2])},
    "onerililen_aksiyonlar": ["Kampanya çeşitliliği artırılmalı", "Rakip analizi güçlendirilmeli"],
    "genel_degerlendirme": "olumlu"
}}"""
                rapor_metni = full_response
                print("[DEBUG] Using manual JSON generation")
        
        return rapor_metni, json_ozet
        
    except Exception as e:
        safe_print(f"[DEBUG] LLM error: {str(e)}")
        # HATA DURUMUNDA MİNİMAL JSON DÖNDÜR (fix script'teki gibi)
        fallback_json = f"""{{
    "ay": {month},
    "yil": {year},
    "toplam_ziyaret": {len(visits) if visits else 0},
    "siparis_sayisi": 0,
    "basari_orani": 0,
    "sunulan_urunler_ve_kampanyalar": [],
    "tespit_edilen_rakipler": [],
    "onerililen_aksiyonlar": ["LLM analizi tekrarlanmalı"],
    "genel_degerlendirme": "analiz_hatasi"
}}"""
        return f"LLM analizi sırasında hata: {str(e)}", fallback_json

def create_monthly_markdown_report(visits: List[Dict], analysis: str, json_summary: str, month: int, year: int, output_path: str):
    """Aylık Markdown raporu oluşturur"""
    
    if not visits:
        print("Rapor oluşturmak için ziyaret verisi bulunamadı")
        return
    
    # Firma bilgilerini al
    firma_info = visits[0]['data']
    firma_adi = firma_info.get('firma_adi', 'Belirtilmemiş')
    gorusulen_kisi = firma_info.get('gorusulen_kisi', 'Belirtilmemiş')
    
    # Mali durum hesaplama - ay içindeki tüm ziyaretlerin ortalaması
    def extract_numeric_value(amount_str):
        """Tutar string'inden sayısal değeri çıkarır (örn: '751594 €' -> 751594)"""
        if not amount_str or amount_str == '—' or amount_str == 'Belirtilmemiş':
            return None
        import re
        numbers = re.findall(r'[\d,]+', str(amount_str))
        if numbers:
            return float(numbers[0].replace(',', ''))
        return None
    
    ciro_2024_values = []
    ciro_2025_values = []
    
    for visit in visits:
        data = visit['data']
        
        ciro_2024 = extract_numeric_value(data.get('ciro_2024'))
        if ciro_2024 is not None:
            ciro_2024_values.append(ciro_2024)
            
        ciro_2025 = extract_numeric_value(data.get('ciro_2025'))
        if ciro_2025 is not None:
            ciro_2025_values.append(ciro_2025)
    
    # Ortalama hesapla
    avg_ciro_2024 = sum(ciro_2024_values) / len(ciro_2024_values) if ciro_2024_values else 0
    avg_ciro_2025 = sum(ciro_2025_values) / len(ciro_2025_values) if ciro_2025_values else 0
    
    # Formatla
    formatted_ciro_2024 = f"{avg_ciro_2024:,.0f} €" if avg_ciro_2024 > 0 else "Belirtilmemiş"
    formatted_ciro_2025 = f"{avg_ciro_2025:,.0f} €" if avg_ciro_2025 > 0 else "Belirtilmemiş"
    
    # Ay ismi
    month_names = {
        '1': 'Ocak', '2': 'Şubat', '3': 'Mart', '4': 'Nisan',
        '5': 'Mayıs', '6': 'Haziran', '7': 'Temmuz', '8': 'Ağustos',
        '9': 'Eylül', '10': 'Ekim', '11': 'Kasım', '12': 'Aralık'
    }
    month_name = month_names.get(str(month), str(month))
    
    report_content = f"""# NormVision Aylık Rapor - {month_name} {year}

**Rapor Oluşturulma Tarihi:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Firma Bilgileri
- **Firma Adı:** {firma_adi}
- **Görüşülen Kişi:** {gorusulen_kisi}
- **Toplam Ziyaret Sayısı:** {len(visits)}
- **Rapor Dönemi:** {month_name} {year}

## Mali Durum (Aylık Ziyaretlerin Ortalaması)
- **Ortalama Ciro 2024:** {formatted_ciro_2024}
- **Ortalama Ciro 2025:** {formatted_ciro_2025}

*Not: Mali durum bilgileri, {month_name} {year} ayı içindeki tüm ziyaretlerde belirtilen ciro değerlerinin aritmetik ortalaması alınarak hesaplanmıştır.*

## Ziyaret Kronolojisi

"""
    
    # Ziyaret detaylarını ekle
    for i, visit in enumerate(visits, 1):
        data = visit['data']
        visit_date = data.get('visit_date', 'Tarih Yok')
        
        report_content += f"""### Ziyaret {i} - {visit_date}

**Temel Bilgiler:**
- **Dosya:** `{visit['pdf_name']}`
- **İşlem Süresi:** {visit['elapsed_seconds']}s

**Mali Durum:**
- **Ciro 2024:** {data.get('ciro_2024', 'Belirtilmemiş')}
- **Ciro 2025:** {data.get('ciro_2025', 'Belirtilmemiş')}

**Ticari Bilgiler:**
- **Sunulan Ürünler/Kampanyalar:** {data.get('sunulan_urun_gruplari_kampanyalar', 'Belirtilmemiş')}
- **Rakip Firma Şartları:** {data.get('rakip_firma_sartlari', 'Belirtilmemiş')}
- **Sipariş Durumu:** {data.get('siparis_alindi_mi', 'Belirtilmemiş')}

**Detaylar:**
> {data.get('genel_yorum', 'Genel yorum bulunamadı')[:500]}{'...' if len(data.get('genel_yorum', '')) > 500 else ''}

---

"""
    
    # LLM analizini ekle
    report_content += f"""
## PROFESYONEL ANALİZ ve ÖNERİLER

{analysis}

## KPI ÖZETİ (Makinece Okunabilir)

Aşağıdaki JSON verileri dashboard entegrasyonu ve KPI takibi için kullanılabilir:

```json
{json_summary}
```

---

**Rapor Sonu - NormVision Aylık Analiz Sistemi**
"""
    
    # Dosyayı kaydet
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

def main():
    parser = argparse.ArgumentParser(description='NormVision - Aylık Rapor Oluşturucu')
    parser.add_argument('--input-dir', required=True, help='PDF dosyalarının bulunduğu klasör')
    parser.add_argument('--month', type=int, choices=range(1, 13), required=True, help='Rapor ayı (1-12)')
    parser.add_argument('--year', type=int, required=True, help='Rapor yılı (örn: 2025)')
    parser.add_argument('--output-dir', default='.', help='Çıktı klasörü (varsayılan: mevcut klasör)')
    parser.add_argument('--llm', action='store_true', help='LLM analizi kullan')
    
    args = parser.parse_args()
    
    # Giriş kontrolü
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists():
        print(f"Hata: Giriş klasörü bulunamadı: {input_dir}")
        sys.exit(1)
    
    # PDF dosyalarını bul (unique paths için set kullan)
    pdf_files = set()
    for ext in ['*.pdf', '*.PDF']:
        pdf_files.update(input_dir.glob(ext))
    
    pdf_files = list(pdf_files)  # Set'i list'e çevir
    
    if not pdf_files:
        print(f"Hata: {input_dir} klasöründe PDF dosyası bulunamadı")
        sys.exit(1)
    
    print(f"Toplam {len(pdf_files)} UNIQUE PDF dosyası bulundu")
    print(f"Hedef dönem: {args.month}/{args.year}")
    
    # PDF'leri işle
    all_visits = []
    for pdf_path in pdf_files:
        print(f"İşleniyor: {pdf_path.name}")
        result = process_single_pdf_for_monthly(str(pdf_path))
        all_visits.append(result)
    
    # Ay ve yıla göre filtrele
    filtered_visits = filter_visits_by_month(all_visits, args.month, args.year)
    
    if not filtered_visits:
        print(f"Hata: {args.month}/{args.year} dönemine ait ziyaret bulunamadı")
        sys.exit(1)
    
    print(f"{args.month}/{args.year} döneminde {len(filtered_visits)} ziyaret bulundu")
    
    # Şirket adını belirle (ilk başarılı ziyaretten al)
    company_name = "UNKNOWN_COMPANY"
    for visit in filtered_visits:
        if visit['status'] == 'SUCCESS':
            raw_company_name = visit['data'].get('firma_adi', '')
            if raw_company_name and raw_company_name not in ['—', 'Belirtilmemiş']:
                company_name = normalize_company_name(raw_company_name)  # Ortak normalizasyon
                break
    
    # Şirket adını güvenli encoding ile yazdır
    try:
        print(f"Sirket adi dosya adlandirmasi icin: {company_name}")
    except UnicodeEncodeError:
        # Türkçe karakterleri ASCII'ye dönüştür
        import unicodedata
        company_name_ascii = unicodedata.normalize('NFKD', company_name).encode('ascii', 'ignore').decode('ascii')
        print(f"Sirket adi dosya adlandirmasi icin: {company_name_ascii}")
    
    # LLM analizi
    analysis = ""
    json_summary = "{}"
    if args.llm:
        print("LLM ile aylık analiz oluşturuluyor...")
        analysis, json_summary = generate_monthly_analysis_with_llm(filtered_visits, args.month, args.year)
    else:
        analysis = "LLM analizi kullanılmadı. --llm parametresi ile detaylı analiz alabilirsiniz."
        json_summary = '{"mesaj": "LLM analizi kullanılmadı"}'
    
    # Rapor oluştur
    month_names = {
        1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan',
        5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos',
        9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
    }
    month_name = month_names.get(args.month, str(args.month))
    
    # Standart Reports klasörünü kullan (.env'den)
    reports_base = os.getenv('REPORTS_BASE', str(output_dir / "Reports" / "Monthly"))
    reports_dir = Path(reports_base) / company_name / f"{args.month:02d}-{month_name}"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"NormVision_Aylik_Rapor_{company_name}_{month_name}_{args.year}_{timestamp}.md"
    report_path = reports_dir / report_filename
    
    create_monthly_markdown_report(filtered_visits, analysis, json_summary, args.month, args.year, str(report_path))
    
    # KPI JSON'unu ayrı dosya olarak kaydet - Şirket adını dahil et
    json_filename = f"NormVision_KPI_{company_name}_{month_name}_{args.year}_{timestamp}.json"
    json_path = reports_dir / json_filename
    
    try:
        # JSON formatını düzelt ve kaydet
        import json
        json_data = json.loads(json_summary)
        
        # Key ismini değiştir (eski key varsa)
        if "ana_kampanyalar" in json_data:
            json_data["sunulan_urunler_ve_kampanyalar"] = json_data.pop("ana_kampanyalar")
        
        # İstenmeyen key'leri kaldır
        if "risk_seviyesi" in json_data:
            json_data.pop("risk_seviyesi")
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"KPI JSON dosyasi olusturuldu: {json_path}")
    except json.JSONDecodeError as e:
        safe_print(f"JSON formati hatali, ham veri kaydediliyor: {str(e)}")
        # Ham veri de mümkünse JSON formatında kaydet
        try:
            # Ham JSON string'i parse etmeyi dene
            fallback_data = json.loads(json_summary)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(fallback_data, f, ensure_ascii=False, indent=2)
        except:
            # Parse edilemezse ham string'i kaydet
            with open(json_path, 'w', encoding='utf-8') as f:
                f.write(json_summary)
        print(f"Ham JSON dosyasi olusturuldu: {json_path}")
    except Exception as e:
        safe_print(f"JSON dosyasi olusturulurken hata: {str(e)}")
    
    print(f"\nAylik rapor olusturuldu: {report_path}")
    print(f"Rapor donemi: {month_name} {args.year}")
    print(f"Analiz edilen ziyaret sayisi: {len(filtered_visits)}")

if __name__ == "__main__":
    main()
