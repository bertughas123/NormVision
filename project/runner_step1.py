# python runner_step1.py "C:/path/to/your.pdf"
from dotenv import load_dotenv
load_dotenv()  # .env dosyasını yükle
import sys
from extractor.pdf_reader import read_pdf_text
from extractor.sections import extract_notlar_block
from extractor.notlar_parser import parse_notlar_kv, declared_keys
from extractor.llm_fill import llm_fill_and_summarize
from extractor.normalize import format_amount

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Kullanım: python runner_step1.py <PDF_PATH>")

    pdf_path = sys.argv[1]
    text = read_pdf_text(pdf_path)
    notlar = extract_notlar_block(text)
    
    # 1. Regex ile parse et
    kv = parse_notlar_kv(notlar)
    
    # 2. Declared keys'leri bul
    declared = declared_keys(notlar)
    
    # 3. LLM ile eksik alanları doldur + özet oluştur
    kv = llm_fill_and_summarize(kv, notlar, declared)

    def get_amt(prefix):
        return format_amount(kv.get(f"{prefix}_value"), kv.get(f"{prefix}_currency"), kv.get(f"{prefix}_raw"))

    print("• 2024 Ciro:", get_amt("ciro_2024"))
    print("• 2025 Ciro:", get_amt("ciro_2025"))
    print("• Q2 Hedef:", get_amt("q2_hedef"))
    print("• Görüşülen Kişi:", kv.get("gorusulen_kisi") or "—")
    print("• Pozisyon:", kv.get("pozisyon") or "—")
    print("• Sunulan Ürün Grupları / Kampanyalar:", kv.get("sunulan_urun_gruplari_kampanyalar") or "—")
    print("• Rakip Firma Şartları:", kv.get("rakip_firma_sartlari") or "—")
    print("• Sipariş Alındı mı?:", kv.get("siparis_alindi_mi") or "—")
    print("• Yaklaşık Sipariş Tutarı:", get_amt("yaklasik_siparis_tutari"))
    print("• Genel Yorum (ham):", kv.get("genel_yorum") or "—")
    print("• Özet:", kv.get("ozet") or "—")
