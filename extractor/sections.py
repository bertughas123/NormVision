import re
import unicodedata
from .normalize import clean

def _fix_dotted_i(s: str) -> str:
    # PDF'ten gelen 'i̇' (kombine noktalı i) problemini düzelt
    s = unicodedata.normalize("NFC", s)
    s = s.replace("i̇", "i").replace("İ", "İ")
    return s

def extract_firma_adi(text: str) -> str | None:
    """PDF'den firma adını çıkarır"""
    # Konu: pattern'ini ara
    konu_pattern = r'(?:KONU|Konu)\s*:\s*(.+?)(?=\s+Müşteri:|$)'
    match = re.search(konu_pattern, text, re.IGNORECASE | re.DOTALL)
    
    if match:
        firm = match.group(1).strip()
        
        # Hukuki kuyrukları temizle
        firm = re.sub(r'\b(TEKN\.HIRD\.LTD\.ŞTİ\.|A\.?\s?Ş\.?|AŞ|LTD\.?\s*ŞTİ\.?|LTD\.?|ŞTİ\.?|STI)\b.*$', '', firm, flags=re.IGNORECASE)
        
        # Temizle ve normalize et
        firm = _fix_dotted_i(clean(firm))
        
        return firm.lower() if firm else None
    
    return None

def extract_notlar_block(text: str) -> str:
    """PDF'den NOTLAR bölümünü çıkarır"""
    
    # Önce "Notlar" başlığından sonraki kısmı bul
    notlar_start = re.search(r'\bNotlar\b', text, re.IGNORECASE)
    if not notlar_start:
        return ""
    
    # Notlar başlığından sonraki metni al
    text_after_notlar = text[notlar_start.end():]
    
    # İlk büyük harfle başlayan satırı bul (genellikle cirolar başlar)
    # "2024 CİROSU" gibi pattern arıyoruz ve MUTABAKAT'a kadar al
    ciro_pattern = r'(20\d{2}\s+[CÇ][İI]ROSU.*?)(?=\s*MUTABAKAT DURUMU|\s*Görevler|\s*Ekler|\n\s*$|\Z)'
    ciro_match = re.search(ciro_pattern, text_after_notlar, re.IGNORECASE | re.DOTALL)
    
    if ciro_match:
        notlar_content = ciro_match.group(1)
        # Temizle ve normalize et
        notlar_content = _fix_dotted_i(clean(notlar_content))
        return notlar_content
    
    # Eğer ciro bulunamazsa, basit pattern kullan ve MUTABAKAT'a kadar al
    simple_pattern = r'([2][0-9]{3}.*?)(?=\s*MUTABAKAT DURUMU|\s*Görevler|\s*Ekler|\n\s*$|\Z)'
    simple_match = re.search(simple_pattern, text_after_notlar, re.DOTALL)
    
    if simple_match:
        notlar_content = simple_match.group(1)
        notlar_content = _fix_dotted_i(clean(notlar_content))
        return notlar_content
    
    return ""
