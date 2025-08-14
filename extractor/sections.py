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
    
    # MUTABAKAT DURUMU'na kadar olan tüm metni al
    # FIX: Basit ve güvenilir pattern - sadece MUTABAKAT DURUMU'na kadar al
    mutabakat_pos = text_after_notlar.find('MUTABAKAT DURUMU')
    
    if mutabakat_pos != -1:
        # MUTABAKAT'a kadar olan kısmı al
        notlar_content = text_after_notlar[:mutabakat_pos]
    else:
        # MUTABAKAT bulunamazsa, Görevler veya Ekler'e kadar al
        gorevler_pos = text_after_notlar.find('Görevler')
        ekler_pos = text_after_notlar.find('Ekler')
        
        end_pos = None
        if gorevler_pos != -1 and ekler_pos != -1:
            end_pos = min(gorevler_pos, ekler_pos)
        elif gorevler_pos != -1:
            end_pos = gorevler_pos
        elif ekler_pos != -1:
            end_pos = ekler_pos
        
        if end_pos:
            notlar_content = text_after_notlar[:end_pos]
        else:
            # Son çare: tüm metni al
            notlar_content = text_after_notlar
    
    # Temizle ve normalize et ama kırpma
    notlar_content = _fix_dotted_i(notlar_content.strip())
    return notlar_content
