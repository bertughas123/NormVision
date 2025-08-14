# python runner_weekly.py --input-dir "<PDF_DIR>" [--llm] [--output-format csv|md]
import argparse
import os
import sys
import csv
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()  # .env dosyasını yükle

from extractor.pdf_reader import read_pdf_text
from extractor.sections import extract_notlar_block, extract_firma_adi
from extractor.notlar_parser import parse_notlar_kv, declared_keys
from extractor.llm_fill import llm_fill_and_summarize
from extractor.normalize import format_amount


def extract_date_from_filename(filename: str) -> datetime | None:
    """Dosya adından tarihi çıkarır (Ziyaret Özeti (Norm)_20250611155220_TR.PDF formatı)"""
    # Pattern: _YYYYMMDDHHMMSS_
    pattern = r'_(\d{8})\d{6}_'
    match = re.search(pattern, filename)
    
    if match:
        date_str = match.group(1)  # YYYYMMDD
        try:
            return datetime.strptime(date_str, '%Y%m%d')
        except ValueError:
            return None
    
    return None


def get_week_key(date: datetime) -> str:
    """Tarihi hafta anahtarına çevirir (YYYY-WW formatı)"""
    year, week, _ = date.isocalendar()
    return f"{year}-W{week:02d}"


def get_week_range(date: datetime) -> tuple[datetime, datetime]:
    """Haftanın başlangıç ve bitiş tarihlerini döndürür"""
    year, week, weekday = date.isocalendar()
    # Haftanın başlangıcı (Pazartesi)
    week_start = date - timedelta(days=weekday - 1)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def process_pdfs_with_dates(input_dir: Path, use_llm: bool = False) -> tuple[dict, list]:
    """PDF'leri işler ve tarihe göre gruplar"""
    pdf_files = list(input_dir.glob("*.pdf")) + list(input_dir.glob("*.PDF"))
    
    weekly_data = defaultdict(list)
    undated_files = []
    
    print(f"📁 {len(pdf_files)} PDF dosyası bulundu")
    
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n📄 [{i}/{len(pdf_files)}] İşleniyor: {pdf_path.name}")
        
        # Tarih çıkar
        file_date = extract_date_from_filename(pdf_path.name)
        
        if not file_date:
            print(f"   ⚠️  Dosya adından tarih çıkarılamadı, atlanıyor")
            undated_files.append(pdf_path.name)
            continue
        
        try:
            # PDF'i işle
            text = read_pdf_text(str(pdf_path))
            firma_adi = extract_firma_adi(text)
            notlar = extract_notlar_block(text)
            kv = parse_notlar_kv(notlar)
            declared = declared_keys(notlar)
            
            if use_llm:
                kv = llm_fill_and_summarize(kv, notlar, declared)
            
            def get_amt(prefix):
                return format_amount(kv.get(f"{prefix}_value"), kv.get(f"{prefix}_currency"), kv.get(f"{prefix}_raw"))
            
            # Hafta anahtarını hesapla
            week_key = get_week_key(file_date)
            
            result = {
                'pdf_name': pdf_path.name,
                'file_date': file_date,
                'week_key': week_key,
                'firma_adi': firma_adi or "—",
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
            
            weekly_data[week_key].append(result)
            print(f"   ✅ Başarılı - Firma: {firma_adi} - Hafta: {week_key}")
            
        except Exception as e:
            print(f"   ❌ Hata: {str(e)}")
    
    return dict(weekly_data), undated_files


def write_weekly_csv(weekly_data: dict, output_path: str):
    """Haftalık veriyi CSV formatında yazar"""
    fieldnames = [
        'week_key', 'week_start', 'week_end', 'pdf_count', 'pdf_name',
        'file_date', 'firma_adi', 'ciro_2024', 'ciro_2025', 'q2_hedef',
        'gorusulen_kisi', 'pozisyon', 'sunulan_urun_gruplari_kampanyalar',
        'rakip_firma_sartlari', 'siparis_alindi_mi', 'yaklasik_siparis_tutari',
        'genel_yorum', 'ozet'
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Haftalara göre sıralı yaz
        for week_key in sorted(weekly_data.keys()):
            week_records = weekly_data[week_key]
            
            # Haftanın tarih aralığını hesapla (ilk kaydın tarihinden)
            first_date = week_records[0]['file_date']
            week_start, week_end = get_week_range(first_date)
            
            for record in sorted(week_records, key=lambda x: x['file_date']):
                row = record.copy()
                row['week_start'] = week_start.strftime('%Y-%m-%d')
                row['week_end'] = week_end.strftime('%Y-%m-%d')
                row['pdf_count'] = len(week_records)
                row['file_date'] = record['file_date'].strftime('%Y-%m-%d')
                writer.writerow(row)


def write_weekly_markdown(weekly_data: dict, output_path: str):
    """Haftalık veriyi Markdown formatında yazar"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Haftalık Ziyaret Özeti Raporu\n\n")
        f.write(f"📅 Rapor oluşturulma: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        
        # Haftalara göre sıralı yaz
        for week_key in sorted(weekly_data.keys()):
            week_records = weekly_data[week_key]
            
            # Haftanın tarih aralığını hesapla
            first_date = week_records[0]['file_date']
            week_start, week_end = get_week_range(first_date)
            
            f.write(f"## 📆 {week_key} ({week_start.strftime('%d.%m.%Y')} - {week_end.strftime('%d.%m.%Y')})\n\n")
            f.write(f"**Toplam ziyaret sayısı:** {len(week_records)}\n\n")
            
            # Her ziyareti detaylı göster
            for i, record in enumerate(sorted(week_records, key=lambda x: x['file_date']), 1):
                f.write(f"### {i}. {record['firma_adi']} - {record['file_date'].strftime('%d.%m.%Y')}\n\n")
                
                f.write("| Alan | Değer |\n")
                f.write("|------|-------|\n")
                f.write(f"| **PDF Dosyası** | `{record['pdf_name']}` |\n")
                f.write(f"| **2024 Ciro** | {record['ciro_2024']} |\n")
                f.write(f"| **2025 Ciro** | {record['ciro_2025']} |\n")
                f.write(f"| **Q2 Hedef** | {record['q2_hedef']} |\n")
                f.write(f"| **Görüşülen Kişi** | {record['gorusulen_kisi']} |\n")
                f.write(f"| **Pozisyon** | {record['pozisyon']} |\n")
                f.write(f"| **Sipariş Alındı mı?** | {record['siparis_alindi_mi']} |\n")
                f.write(f"| **Yaklaşık Sipariş Tutarı** | {record['yaklasik_siparis_tutari']} |\n")
                
                if record['sunulan_urun_gruplari_kampanyalar'] != "—":
                    f.write(f"| **Sunulan Ürün Grupları** | {record['sunulan_urun_gruplari_kampanyalar']} |\n")
                
                if record['rakip_firma_sartlari'] != "—":
                    f.write(f"| **Rakip Firma Şartları** | {record['rakip_firma_sartlari']} |\n")
                
                if record['ozet'] != "—":
                    f.write(f"| **Özet** | {record['ozet']} |\n")
                
                f.write("\n")
                
                # Genel yorum varsa ayrı bir bölümde göster
                if record['genel_yorum'] != "—":
                    f.write("**💬 Genel Yorum:**\n")
                    f.write(f"```\n{record['genel_yorum']}\n```\n\n")
                
                f.write("---\n\n")


def main():
    parser = argparse.ArgumentParser(description='Haftalık timeline bazında PDF analizi')
    parser.add_argument('--input-dir', required=True, help='PDF dosyalarının bulunduğu klasör')
    parser.add_argument('--llm', action='store_true', help='LLM ile eksik alanları doldur')
    parser.add_argument('--output-format', choices=['csv', 'md', 'both'], default='both', 
                       help='Çıktı formatı (csv/md/both)')
    parser.add_argument('--output-dir', default='.', help='Çıktı dosyalarının kaydedileceği klasör')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists():
        print(f"❌ Hata: Giriş klasörü bulunamadı: {input_dir}")
        sys.exit(1)
    
    print(f"🔧 LLM kullanımı: {'AÇIK' if args.llm else 'KAPALI'}")
    print(f"📊 Çıktı formatı: {args.output_format}")
    
    # PDF'leri işle ve tarihe göre grupla
    weekly_data, undated_files = process_pdfs_with_dates(input_dir, args.llm)
    
    if not weekly_data:
        print("\n❌ İşlenecek tarihli dosya bulunamadı")
        sys.exit(1)
    
    # Çıktı dosyalarını oluştur
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if args.output_format in ['csv', 'both']:
        csv_path = output_dir / f"weekly_timeline_{timestamp}.csv"
        write_weekly_csv(weekly_data, str(csv_path))
        print(f"\n📊 CSV raporu kaydedildi: {csv_path}")
    
    if args.output_format in ['md', 'both']:
        md_path = output_dir / f"weekly_timeline_{timestamp}.md"
        write_weekly_markdown(weekly_data, str(md_path))
        print(f"📝 Markdown raporu kaydedildi: {md_path}")
    
    # İstatistikler
    total_weeks = len(weekly_data)
    total_visits = sum(len(records) for records in weekly_data.values())
    firms = set()
    for records in weekly_data.values():
        for record in records:
            if record['firma_adi'] != "—":
                firms.add(record['firma_adi'])
    
    print(f"\n📋 Haftalık Analiz Tamamlandı:")
    print(f"   • Toplam hafta sayısı: {total_weeks}")
    print(f"   • Toplam ziyaret sayısı: {total_visits}")
    print(f"   • Benzersiz firma sayısı: {len(firms)}")
    
    if undated_files:
        print(f"   • Tarihsiz dosya sayısı: {len(undated_files)}")
        print("   • Tarihsiz dosyalar:")
        for filename in undated_files:
            print(f"     - {filename}")
    
    # Haftalık dağılım
    print(f"\n📆 Haftalık Dağılım:")
    for week_key in sorted(weekly_data.keys()):
        week_records = weekly_data[week_key]
        first_date = week_records[0]['file_date']
        week_start, week_end = get_week_range(first_date)
        print(f"   • {week_key} ({week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}): {len(week_records)} ziyaret")


if __name__ == "__main__":
    main()
