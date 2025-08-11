from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal

class NotlarModel(BaseModel):
    # Numerik alanlar: value + currency + raw (opsiyonel)
    ciro_2024_value: Optional[Decimal] = None
    ciro_2024_currency: Optional[str] = None
    ciro_2024_raw: Optional[str] = None

    ciro_2025_value: Optional[Decimal] = None
    ciro_2025_currency: Optional[str] = None
    ciro_2025_raw: Optional[str] = None

    q2_hedef_value: Optional[Decimal] = None
    q2_hedef_currency: Optional[str] = None
    q2_hedef_raw: Optional[str] = None

    yaklasik_siparis_tutari_value: Optional[Decimal] = None
    yaklasik_siparis_tutari_currency: Optional[str] = None
    yaklasik_siparis_tutari_raw: Optional[str] = None

    # Metin alanlar
    gorusulen_kisi: Optional[str] = None
    pozisyon: Optional[str] = None
    sunulan_urun_gruplari_kampanyalar: Optional[str] = None
    rakip_firma_sartlari: Optional[str] = None
    siparis_alindi_mi: Optional[str] = None
    siparis_alinamayan_urunler_ve_nedenleri: Optional[str] = None
    genel_yorum: Optional[str] = None
    ozet: Optional[str] = None

class VisitRecord(BaseModel):
    firma_adi: str = Field(..., description="PDF 'Konu' alanı (sade)")
    notlar: NotlarModel
