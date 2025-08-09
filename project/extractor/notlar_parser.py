import re
from .normalize import parse_amount

def declared_keys(notlar_text: str) -> list:
    """PDF'ten key: başlıklarını toplar ve kanonik isimlere map'ler"""
    if not notlar_text:
        return []
    
    # "KEY:" pattern'ini bul
    key_patterns = re.findall(r'([^:]*?):', notlar_text, re.IGNORECASE)
    
    canonical_keys = []
    
    for key in key_patterns:
        key_clean = key.strip().lower()
        
        # Kanonik mapping - TÜM alanları dahil et
        if any(x in key_clean for x in ['2024', 'ciro']):
            canonical_keys.append('ciro_2024')
        elif any(x in key_clean for x in ['2025', 'ciro']):
            canonical_keys.append('ciro_2025')
        elif any(x in key_clean for x in ['q2', 'hedef']):
            canonical_keys.append('q2_hedef')
        elif any(x in key_clean for x in ['görüşülen', 'gorusulen', 'kişi', 'kisi']):
            canonical_keys.append('gorusulen_kisi')
        elif any(x in key_clean for x in ['pozisyon', 'position']):
            canonical_keys.append('pozisyon')
        elif any(x in key_clean for x in ['sunulan', 'ürün', 'urun', 'grup', 'kampanya']):
            canonical_keys.append('sunulan_urun_gruplari_kampanyalar')
        elif any(x in key_clean for x in ['rakip', 'firma', 'şart', 'sart']):
            canonical_keys.append('rakip_firma_sartlari')
        elif any(x in key_clean for x in ['sipariş', 'siparis', 'alındı', 'alindi']) and 'mi' in key_clean:
            canonical_keys.append('siparis_alindi_mi')
        elif any(x in key_clean for x in ['yaklaşık', 'yaklasik', 'tutar']):
            canonical_keys.append('yaklasik_siparis_tutari')
        elif any(x in key_clean for x in ['alinamayan', 'ürünler', 'urunler', 'neden']):
            canonical_keys.append('siparis_alinamayan_urunler_ve_nedenleri')
    
    # Duplicate'leri kaldır ve sırala
    return list(dict.fromkeys(canonical_keys))

def parse_notlar_kv(notlar_text: str) -> dict:
    """Notlar metninden key-value çiftlerini çıkarır"""
    if not notlar_text:
        return {}
    
    kv = {}
    
    # 2024 Cirosu
    match = re.search(r'2024\s+[cç]irosu\s+kümülatif\s*:\s*([^€\n]+€?)', notlar_text, re.IGNORECASE)
    if match:
        amount_str = match.group(1).strip()
        value, currency = parse_amount(amount_str)
        kv["ciro_2024_value"] = value
        kv["ciro_2024_currency"] = currency
        kv["ciro_2024_raw"] = amount_str
    
    # 2025 Cirosu
    match = re.search(r'2025\s+[cç]irosu\s+kümülatif\s*:\s*([^€\n]+€?)', notlar_text, re.IGNORECASE)
    if match:
        amount_str = match.group(1).strip()
        value, currency = parse_amount(amount_str)
        kv["ciro_2025_value"] = value
        kv["ciro_2025_currency"] = currency
        kv["ciro_2025_raw"] = amount_str
    
    # Q2 Hedef
    match = re.search(r'q2\s+hedef\s*:\s*([^€\n]+€?)', notlar_text, re.IGNORECASE)
    if match:
        amount_str = match.group(1).strip()
        value, currency = parse_amount(amount_str)
        kv["q2_hedef_value"] = value
        kv["q2_hedef_currency"] = currency
        kv["q2_hedef_raw"] = amount_str
    
    # Görüşülen Kişi
    match = re.search(r'görüşülen\s+kişi\s+ad[ıi]\s*:\s*([^:]+?)(?=\s+pozi[sz]yon|$)', notlar_text, re.IGNORECASE)
    if match:
        kv["gorusulen_kisi"] = match.group(1).strip()
    
    # Pozisyon
    match = re.search(r'pozi[sz]yon[uy]*\s*:\s*([^:]+?)(?=\s+sunulan|$)', notlar_text, re.IGNORECASE)
    if match:
        kv["pozisyon"] = match.group(1).strip()
    
    # Sunulan Ürün Grupları - boş alanları kontrol et
    match = re.search(r'sunulan\s+ürün\s+gruplari\s*/?\s*kampanyalar\s*:\s*([^:]*?)(?=\s+fi[rı]mada\s+karşilaşilan|$)', notlar_text, re.IGNORECASE)
    if match:
        content = match.group(1).strip()
        if content and not re.match(r'^[A-ZĞÜŞÖÇI\s]+$', content):
            kv["sunulan_urun_gruplari_kampanyalar"] = content
        else:
            kv["sunulan_urun_gruplari_kampanyalar"] = "—"
    
    # Rakip Firma Şartları - boş alanları kontrol et
    match = re.search(r'fi[rı]mada\s+karşilaşilan\s+raki[bp]\s+fi[rı]ma\s+şartlari\s*:\s*([^:]*?)(?=\s+si[bp]ariş\s+alind[ıi]|$)', notlar_text, re.IGNORECASE)
    if match:
        content = match.group(1).strip()
        if content and not re.match(r'^[A-ZĞÜŞÖÇI\s]+$', content):
            kv["rakip_firma_sartlari"] = content
        else:
            kv["rakip_firma_sartlari"] = "—"
    
    # Sipariş Alındı mı - boş alanları kontrol et
    match = re.search(r'si[bp]ariş\s+alind[ıi]\s+mi\s*\?\s*([^:]*?)(?=\s+yaklaşik|$)', notlar_text, re.IGNORECASE)
    if match:
        content = match.group(1).strip()
        if content and not re.match(r'^[A-ZĞÜŞÖÇI\s]+$', content):
            kv["siparis_alindi_mi"] = content
        else:
            kv["siparis_alindi_mi"] = "—"
    
    # Yaklaşık Sipariş Tutarı
    match = re.search(r'yaklaşik\s+si[bp]ariş\s+tutari\s*:\s*([^:]*?)(?=\s+si[bp]ariş\s+alinamayan|$)', notlar_text, re.IGNORECASE)
    if match:
        content = match.group(1).strip()
        if content and not re.match(r'^[A-ZĞÜŞÖÇI\s]+$', content):
            amount_str = content
            value, currency = parse_amount(amount_str)
            kv["yaklasik_siparis_tutari_value"] = value
            kv["yaklasik_siparis_tutari_currency"] = currency
            kv["yaklasik_siparis_tutari_raw"] = amount_str
        else:
            kv["yaklasik_siparis_tutari_raw"] = "—"
    
    # Genel Yorum
    match = re.search(r'fi[rı]ma\s+hakkinda\s+genel\s+yorum\s*:\s*(.+)', notlar_text, re.IGNORECASE | re.DOTALL)
    if match:
        kv["genel_yorum"] = match.group(1).strip()
    
    return kv
