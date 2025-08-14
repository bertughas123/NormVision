# python runner_batch.py --input-dir "<PDF_DIR>" [--llm] [--firm-filter "regex"] [--markdown]
import argparse
import os
import sys
import csv
import time
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()  # .env dosyasını yükle

from extractor.pdf_reader import read_pdf_text
from extractor.sections import extract_notlar_block, extract_firma_adi
from extractor.notlar_parser import parse_notlar_kv, declared_keys
from extractor.llm_fill import llm_fill_and_summarize
from extractor.normalize import format_amount


def process_single_pdf(pdf_path: str, use_llm: bool = False) -> dict:
    """Tek bir PDF'i işler ve sonuçları döndürür"""
    start_time = time.time()
    
    try:
        # PDF'i oku
        text = read_pdf_text(pdf_path)
        
        # Firma adını çıkar
        firma_adi = extract_firma_adi(text)
        
        # Notlar bloğunu çıkar
        notlar = extract_notlar_block(text)
        
        # Regex ile parse et
        kv = parse_notlar_kv(notlar)
        
        # Declared keys'leri bul
        declared = declared_keys(notlar)
        
        # LLM ile eksik alanları doldur (isteğe bağlı)
        if use_llm:
            kv = llm_fill_and_summarize(kv, notlar, declared)
        
        def get_amt(prefix):
            return format_amount(kv.get(f"{prefix}_value"), kv.get(f"{prefix}_currency"), kv.get(f"{prefix}_raw"))
        
        elapsed = time.time() - start_time
        
        result = {
            'pdf_path': pdf_path,
            'pdf_name': os.path.basename(pdf_path),
            'status': 'SUCCESS',
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
            'ozet': kv.get("ozet") or "—",
            'llm_used': use_llm,
            'elapsed_seconds': round(elapsed, 2),
            'processed_at': datetime.now().isoformat()
        }
        
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            'pdf_path': pdf_path,
            'pdf_name': os.path.basename(pdf_path),
            'status': 'ERROR',
            'error_message': str(e),
            'firma_adi': "—",
            'llm_used': use_llm,
            'elapsed_seconds': round(elapsed, 2),
            'processed_at': datetime.now().isoformat()
        }


def write_batch_logs(results: list, output_path: str):
    """Batch işlem loglarını CSV'ye yazar"""
    fieldnames = [
        'pdf_name', 'pdf_path', 'status', 'firma_adi', 
        'ciro_2024', 'ciro_2025', 'q2_hedef',
        'gorusulen_kisi', 'pozisyon', 
        'sunulan_urun_gruplari_kampanyalar',
        'rakip_firma_sartlari', 'siparis_alindi_mi',
        'yaklasik_siparis_tutari', 'genel_yorum', 'ozet',
        'llm_used', 'elapsed_seconds', 'processed_at', 'error_message'
    ]
    
    # Increase CSV field size limit for large text fields
    import csv
    csv.field_size_limit(1000000)  # 1MB limit for large text fields
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            # Ensure long text fields are properly handled
            clean_result = result.copy()
            if 'genel_yorum' in clean_result and clean_result['genel_yorum']:
                # Keep full text, just ensure it's properly encoded
                clean_result['genel_yorum'] = str(clean_result['genel_yorum'])
            writer.writerow(clean_result)


def create_summary_by_firma(results: list, output_path: str):
    """Firma bazında özet rapor oluşturur"""
    firma_summary = defaultdict(list)
    
    # Başarılı sonuçları firma bazında grupla
    for result in results:
        if result['status'] == 'SUCCESS' and result['firma_adi'] != "—":
            firma_summary[result['firma_adi']].append(result)
    
    # Özet CSV'yi yaz
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'firma_adi', 'pdf_count', 'pdf_names',
            'latest_ciro_2024', 'latest_ciro_2025', 'latest_q2_hedef',
            'unique_contacts', 'latest_siparis_status',
            'combined_ozet', 'latest_processed_at'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for firma_adi, firma_results in firma_summary.items():
            # En son işlenen PDF'i bul
            latest = max(firma_results, key=lambda x: x['processed_at'])
            
            # Benzersiz kişileri topla
            contacts = set()
            for r in firma_results:
                if r['gorusulen_kisi'] and r['gorusulen_kisi'] != "—":
                    contacts.add(r['gorusulen_kisi'])
            
            # Özetleri birleştir
            ozetler = []
            for r in firma_results:
                if r['ozet'] and r['ozet'] != "—":
                    ozetler.append(f"[{r['pdf_name']}]: {r['ozet']}")
            
            summary_row = {
                'firma_adi': firma_adi,
                'pdf_count': len(firma_results),
                'pdf_names': '; '.join([r['pdf_name'] for r in firma_results]),
                'latest_ciro_2024': latest.get('ciro_2024', '—'),
                'latest_ciro_2025': latest.get('ciro_2025', '—'),
                'latest_q2_hedef': latest.get('q2_hedef', '—'),
                'unique_contacts': '; '.join(sorted(contacts)) if contacts else '—',
                'latest_siparis_status': latest.get('siparis_alindi_mi', '—'),
                'combined_ozet': ' | '.join(ozetler) if ozetler else '—',
                'latest_processed_at': latest['processed_at']
            }
            
            writer.writerow(summary_row)


def format_currency(value):
    """Para birimi formatını düzenle"""
    if not value or value == "—":
        return "—"
    return value


def format_date_from_filename(filename):
    """Dosya adından tarihi çıkar ve formatla"""
    try:
        # Ziyaret Özeti (Norm)_20250611155220_TR.PDF -> 2025-06-11
        parts = filename.split('_')
        if len(parts) >= 2:
            date_str = parts[1][:8]  # 20250611
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            return f"{year}-{month}-{day}"
    except:
        pass
    return "Tarih bilinmiyor"


def create_markdown_report(results: list, output_path: str):
    """Batch sonuçlarından Markdown raporu oluştur"""
    
    # Firma bazında grupla
    firma_groups = defaultdict(list)
    for result in results:
        if result['status'] == 'SUCCESS' and result['firma_adi'] != "—":
            firma_groups[result['firma_adi']].append(result)
    
    # Markdown dosyasını oluştur
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Batch İşlem Raporu\n\n")
        f.write(f"**Oluşturulma Tarihi:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Toplam Firma Sayısı:** {len(firma_groups)}\n")
        f.write(f"**Toplam Ziyaret Sayısı:** {sum(len(visits) for visits in firma_groups.values())}\n\n")
        
        f.write("---\n\n")
        
        # Her firma için ayrı bölüm
        for firma_adi, visits in firma_groups.items():
            f.write(f"## 🏢 {firma_adi}\n\n")
            
            # Firma özet bilgileri
            latest_visit = max(visits, key=lambda x: x['pdf_name'])
            f.write(f"**Toplam Ziyaret:** {len(visits)}\n")
            f.write(f"**Son Ciro 2024:** {format_currency(latest_visit['ciro_2024'])}\n")
            f.write(f"**Son Ciro 2025:** {format_currency(latest_visit['ciro_2025'])}\n")
            f.write(f"**Görüşülen Kişi:** {latest_visit['gorusulen_kisi']} ({latest_visit['pozisyon']})\n\n")
            
            # Ziyaretleri tarihe göre sırala
            visits_sorted = sorted(visits, key=lambda x: x['pdf_name'])
            
            for i, visit in enumerate(visits_sorted, 1):
                visit_date = format_date_from_filename(visit['pdf_name'])
                f.write(f"### 📅 Ziyaret {i} - {visit_date}\n\n")
                
                # Temel bilgiler
                f.write("**Temel Bilgiler:**\n")
                f.write(f"- **Tarih:** {visit_date}\n")
                f.write(f"- **Dosya:** `{visit['pdf_name']}`\n")
                f.write(f"- **İşlem Süresi:** {visit['elapsed_seconds']}s\n\n")
                
                # Mali bilgiler
                f.write("**Mali Durum:**\n")
                f.write(f"- **Ciro 2024:** {format_currency(visit['ciro_2024'])}\n")
                f.write(f"- **Ciro 2025:** {format_currency(visit['ciro_2025'])}\n")
                if visit['q2_hedef'] and visit['q2_hedef'] != "—":
                    f.write(f"- **Q2 Hedef:** {format_currency(visit['q2_hedef'])}\n")
                if visit['yaklasik_siparis_tutari'] and visit['yaklasik_siparis_tutari'] != "—":
                    f.write(f"- **Yaklaşık Sipariş Tutarı:** {format_currency(visit['yaklasik_siparis_tutari'])}\n")
                f.write("\n")
                
                # Ticari bilgiler
                f.write("**Ticari Bilgiler:**\n")
                if visit['sunulan_urun_gruplari_kampanyalar'] and visit['sunulan_urun_gruplari_kampanyalar'] != "—":
                    f.write(f"- **Sunulan Ürünler/Kampanyalar:** {visit['sunulan_urun_gruplari_kampanyalar']}\n")
                if visit['rakip_firma_sartlari'] and visit['rakip_firma_sartlari'] != "—":
                    f.write(f"- **Rakip Firma Şartları:** {visit['rakip_firma_sartlari']}\n")
                if visit['siparis_alindi_mi'] and visit['siparis_alindi_mi'] != "—":
                    f.write(f"- **Sipariş Durumu:** {visit['siparis_alindi_mi']}\n")
                f.write("\n")
                
                # Genel yorum - FULL TEXT without truncation
                if visit['genel_yorum'] and visit['genel_yorum'] != "—":
                    f.write("**Detaylar:**\n\n")
                    # Ensure full text is written with proper line breaks
                    full_comment = visit['genel_yorum'].strip()
                    # Replace any potential line breaks with proper markdown formatting
                    formatted_comment = full_comment.replace('\n', '\n> ')
                    f.write(f"> {formatted_comment}\n\n")
                
                # AI Özeti
                if visit['ozet'] and visit['ozet'] != "—":
                    f.write("**🤖 AI Özeti:**\n")
                    f.write(f"> {visit['ozet']}\n\n")
                
                f.write("---\n\n")
            
            f.write("\n")


def main():
    parser = argparse.ArgumentParser(description='Batch PDF işleme ve loglama')
    parser.add_argument('--input-dir', required=True, help='PDF dosyalarının bulunduğu klasör')
    parser.add_argument('--llm', action='store_true', help='LLM ile eksik alanları doldur')
    parser.add_argument('--firm-filter', help='Firma adı regex filtresi')
    parser.add_argument('--output-dir', default='.', help='Çıktı dosyalarının kaydedileceği klasör')
    parser.add_argument('--markdown', action='store_true', help='Markdown raporu da oluştur')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists():
        print(f"❌ Hata: Giriş klasörü bulunamadı: {input_dir}")
        sys.exit(1)
    
    # PDF dosyalarını bul - DÜZELTME: Case-insensitive unique collection
    pdf_files = []
    pdf_names_seen = set()
    
    # First collect .pdf files
    for pdf_file in input_dir.glob("*.pdf"):
        name_lower = pdf_file.name.lower()
        if name_lower not in pdf_names_seen:
            pdf_files.append(pdf_file)
            pdf_names_seen.add(name_lower)
    
    # Then collect .PDF files (only if not already seen)
    for pdf_file in input_dir.glob("*.PDF"):
        name_lower = pdf_file.name.lower()
        if name_lower not in pdf_names_seen:
            pdf_files.append(pdf_file)
            pdf_names_seen.add(name_lower)
    
    # Sort the final list
    pdf_files = sorted(pdf_files)
    
    if not pdf_files:
        print(f"❌ Hata: {input_dir} klasöründe PDF dosyası bulunamadı")
        sys.exit(1)
    
    print(f"📁 {len(pdf_files)} UNIQUE PDF dosyası bulundu:")
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"   {i:2d}. {pdf_file.name}")
    
    print(f"🔧 LLM kullanımı: {'AÇIK' if args.llm else 'KAPALI'}")
    print(f"📄 Markdown raporu: {'AÇIK' if args.markdown else 'KAPALI'}")
    
    if args.firm_filter:
        print(f"🔍 Firma filtresi: {args.firm_filter}")
    
    # PDF'leri işle
    results = []
    firm_filter_regex = re.compile(args.firm_filter, re.IGNORECASE) if args.firm_filter else None
    
    total_files = len(pdf_files)
    
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n📄 [{i}/{total_files}] İşleniyor: {pdf_path.name}")
        
        # LLM rate limit hatası için basit retry mekanizması
        max_retries = 3
        retry_delay = 30  # saniye
        for attempt in range(max_retries):
            try:
                result = process_single_pdf(str(pdf_path), args.llm)
                break
            except Exception as e:
                if "ResourceExhausted" in str(e) and attempt < max_retries - 1:
                    print(f"   ⚠️ API rate limit aşıldı. {retry_delay} saniye bekleniyor... ({attempt+1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    result = {
                        'pdf_path': str(pdf_path),
                        'pdf_name': pdf_path.name,
                        'status': 'ERROR',
                        'error_message': str(e),
                        'firma_adi': "—",
                        'llm_used': args.llm,
                        'elapsed_seconds': 0,
                        'processed_at': datetime.now().isoformat()
                    }
        
        # Firma filtresi kontrolü
        if firm_filter_regex and result['status'] == 'SUCCESS':
            if not firm_filter_regex.search(result['firma_adi']):
                print(f"   ⏭️  Firma filtresi eşleşmedi, atlanıyor")
                continue
        
        results.append(result)
        
        if result['status'] == 'SUCCESS':
            print(f"   ✅ Başarılı - Firma: {result['firma_adi']} - Süre: {result['elapsed_seconds']}s")
        else:
            print(f"   ❌ Hata: {result.get('error_message', 'Bilinmeyen hata')}")
    
    if not results:
        print("\n❌ İşlenecek dosya kalmadı")
        sys.exit(0)
    
    # Çıktı dosyalarını oluştur
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # batch_logs.csv
    logs_path = output_dir / f"batch_logs_{timestamp}.csv"
    write_batch_logs(results, str(logs_path))
    print(f"\n📊 Batch logları kaydedildi: {logs_path}")
    
    # summary_by_firma.csv
    summary_path = output_dir / f"summary_by_firma_{timestamp}.csv"
    create_summary_by_firma(results, str(summary_path))
    print(f"📈 Firma özeti kaydedildi: {summary_path}")
    
    # Markdown raporu (isteğe bağlı)
    if args.markdown:
        markdown_path = output_dir / f"batch_report_{timestamp}.md"
        create_markdown_report(results, str(markdown_path))
        print(f"📄 Markdown raporu kaydedildi: {markdown_path}")
    
    # İstatistikler
    successful = len([r for r in results if r['status'] == 'SUCCESS'])
    failed = len([r for r in results if r['status'] == 'ERROR'])
    total_time = sum([r['elapsed_seconds'] for r in results])
    
    print(f"\n📋 İşlem Tamamlandı:")
    print(f"   • Toplam: {len(results)} dosya")
    print(f"   • Başarılı: {successful}")
    print(f"   • Hatalı: {failed}")
    print(f"   • Toplam süre: {total_time:.1f}s")
    print(f"   • Ortalama süre: {total_time/len(results):.1f}s")


if __name__ == "__main__":
    main()
