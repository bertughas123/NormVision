# Normalize module
import re
from decimal import Decimal
from typing import Optional, Tuple

def clean(text):
    """Metni temizler ve normalize eder"""
    if not text:
        return ""
    
    # Fazla boşlukları temizle
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Başında ve sonunda boşlukları kaldır
    text = text.strip()
    
    return text


CURRENCY_TOKENS = ["€", "TL", "₺", "TRY", "EUR", "Euro", "eur", "euro"]

def normalize_tr(s: str) -> str:
    return (s.lower()
            .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
            .replace("ü", "u").replace("ö", "o").replace("ç", "c"))

def parse_amount(value_str: Optional[str]) -> Tuple[Optional[Decimal], Optional[str]]:
    """Metinden sayıyı Decimal'a çevir ve para birimi sembolünü ayıkla.
    Dönen: (Decimal|None, currency|None). Ör: "751.594 €" -> (Decimal('751.594'), '€')
    """
    if not value_str:
        return None, None
    s = value_str.strip()

    # Para birimi tespiti
    cur = None
    for tok in CURRENCY_TOKENS:
        if tok in s or tok.lower() in s.lower():
            cur = "€" if tok.lower() in ("eur", "euro") else ("₺" if tok in ("₺", "TL", "TRY") else tok)
            break

    # Yalnızca rakam ve ayraçları bırak
    digits = re.sub(r"[^0-9,\.]", "", s)
    if not digits:
        return None, cur

    # Hem virgül hem nokta varsa: son görüleni ondalık kabul et
    if "," in digits and "." in digits:
        last = max(digits.rfind(","), digits.rfind("."))
        int_part = re.sub(r"\D", "", digits[:last])
        dec_part = re.sub(r"\D", "", digits[last+1:])
        canonical = f"{int_part}.{dec_part}" if dec_part else int_part
    else:
        canonical = digits.replace(".", "").replace(",", ".")

    try:
        return Decimal(canonical), cur
    except Exception:
        return None, cur

def format_amount(value: Optional[Decimal], currency: Optional[str], raw: Optional[str] = None) -> str:
    """Gösterim: varsa Decimal + currency, yoksa raw, o da yoksa '—'"""
    if value is not None:
        return f"{value} {currency}".strip()
    return raw or "—"