#!/usr/bin/env python3
"""
Ortak şirket adı normalizasyon fonksiyonları
Her iki modül (runner_monthly ve final_assembler) aynı kanonikleştirme kullanacak
"""

import unicodedata
import re

def normalize_company_name(company_name: str) -> str:
    """
    Şirket adını klasör adı için kanonik hale getirir (nokta ve tire korunur)
    
    Args:
        company_name: Ham şirket adı (örn: "Şirinler Bağlantı Elem.-Boya")
        
    Returns:
        Normalize edilmiş şirket adı (örn: "SIRINLER_BAGLANTI_ELEM.-BOYA")
    """
    if not company_name:
        return "UNKNOWN_COMPANY"
    
    # 1. NFKD normalizasyonu + diakritik karakter temizleme
    normalized = unicodedata.normalize('NFKD', company_name)
    
    # 2. Türkçe karakter dönüşümleri (kesin dönüşümler)
    char_map = {
        'Ş': 'S', 'ş': 's',
        'İ': 'I', 'ı': 'i',  # ı→i, İ→I
        'Ğ': 'G', 'ğ': 'g',
        'Ü': 'U', 'ü': 'u',
        'Ö': 'O', 'ö': 'o',
        'Ç': 'C', 'ç': 'c',
    }
    
    result = ""
    for char in normalized:
        if char in char_map:
            result += char_map[char]
        elif unicodedata.category(char) != 'Mn':  # Diakritik karakterleri atla
            result += char
    
    # 3. Dash varyantlarını normalize et (em-dash, en-dash → normal dash)
    result = re.sub(r'[–—−]', '-', result)
    
    # 4. Büyük harfe çevir
    result = result.upper()
    
    # 5. Klasör adı için: sadece boşlukları underscore yap, nokta ve tire koru
    result = re.sub(r'\s+', '_', result)
    
    # 6. Güvenli olmayan karakterleri temizle (harf, rakam, underscore, nokta, tire kalsın)
    result = re.sub(r'[^A-Z0-9_.-]', '', result)
    
    # 7. Ardışık ayraçları daralt
    result = re.sub(r'_{2,}', '_', result)
    result = re.sub(r'\.{2,}', '.', result)
    result = re.sub(r'-{2,}', '-', result)
    
    # 8. Baş/son ayraçları temizle
    result = result.strip('_.-')
    
    # 9. Uzunluk limiti (Windows klasör adı limiti)
    if len(result) > 100:
        result = result[:100].rstrip('_.-')
    
    return result or "UNKNOWN_COMPANY"

def normalize_for_filename(company_name: str) -> str:
    """
    Dosya adı için güvenli normalizasyon (nokta ve tire de underscore olur)
    
    Args:
        company_name: Ham şirket adı
        
    Returns:
        Dosya adı için güvenli şirket adı (örn: "SIRINLER_BAGLANTI_ELEM_BOYA")
    """
    # Önce klasör normalizasyonu yap
    normalized = normalize_company_name(company_name)
    
    # Dosya adı için nokta ve tireyi de underscore yap
    normalized = normalized.replace('.', '_').replace('-', '_')
    
    # Ardışık underscoreları daralt
    normalized = re.sub(r'_{2,}', '_', normalized)
    
    # Baş/son underscoreları temizle
    normalized = normalized.strip('_')
    
    return normalized or "UNKNOWN_COMPANY"

# Test fonksiyonu
def test_normalization():
    """Test cases"""
    test_cases = [
        "Şirinler Bağlantı Elem.-Boya",
        "NORM HOLDING A.Ş.",
        "ABC İnşaat Ltd. Şti.",
        "Özel Çelik San. & Tic.",
    ]
    
    print("=== COMPANY NAME NORMALIZATION TESTS ===")
    for original in test_cases:
        folder_name = normalize_company_name(original)
        file_name = normalize_for_filename(original)
        print(f"Original: '{original}'")
        print(f"  → Folder: '{folder_name}'")
        print(f"  → File:   '{file_name}'")
        print()

if __name__ == "__main__":
    test_normalization()
