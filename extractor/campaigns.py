# campaigns.py - Aylık satış kampanyaları yapılandırması
"""
Bu dosya her ay güncellenen satış kampanyalarını içerir.
LLM özet oluştururken bu kampanyaların ziyaret raporunda geçip geçmediğini kontrol eder.
"""

from datetime import datetime
from typing import Dict, List

# Mevcut ay kampanyaları (Ağustos 2025)
CURRENT_MONTH_CAMPAIGNS = {
    "month": "2025-08",  # YYYY-MM formatı
    "campaigns": {
        "zimba_tabancasi": {
            "name": "Zımba Tabancası Özel Fiyat",
            "description": "Zımba Tabancasına özel fiyat (1000 TL)",
            "keywords": ["zımba", "zımba tabancası", "zimba", "zimba tabancası", "1000 tl", "1.000 tl"],
            "price": "1000 TL",
            "type": "özel_fiyat"
        },
        "vida_iskonto": {
            "name": "Vida Ürünleri İskonto",
            "description": "Vida ürünlerinde özel iskonto (%54)",
            "keywords": ["vida", "%54", "54", "iskonto", "indirim", "vida iskonto"],
            "discount": "%54",
            "type": "iskonto"
        }
    }
}

# Kampanya geçmişi (gelecek aylar için referans)
CAMPAIGN_HISTORY = {
    "2025-07": {
        "campaigns": {
            # Önceki ay kampanyaları buraya eklenecek
        }
    }
    # Diğer aylar eklenecek...
}

def get_current_campaigns() -> Dict:
    """Mevcut ayın kampanyalarını döndür"""
    current_month = datetime.now().strftime("%Y-%m")
    
    if CURRENT_MONTH_CAMPAIGNS["month"] == current_month:
        return CURRENT_MONTH_CAMPAIGNS["campaigns"]
    else:
        # Kampanya tarihi geçmişse uyarı ver
        print(f"⚠️ UYARI: Kampanya tarihi güncel değil. Mevcut: {current_month}, Tanımlı: {CURRENT_MONTH_CAMPAIGNS['month']}")
        return {}

def check_campaign_mentions(text: str) -> Dict[str, bool]:
    """Metinde kampanya unsurlarının geçip geçmediğini kontrol et"""
    if not text:
        return {}
    
    text_lower = text.lower()
    campaigns = get_current_campaigns()
    
    campaign_checks = {}
    
    for campaign_key, campaign_info in campaigns.items():
        mentioned = any(keyword in text_lower for keyword in campaign_info["keywords"])
        campaign_checks[campaign_key] = {
            "mentioned": mentioned,
            "name": campaign_info["name"],
            "description": campaign_info["description"]
        }
    
    return campaign_checks

def get_campaign_summary() -> str:
    """Mevcut kampanyaların özetini döndür"""
    campaigns = get_current_campaigns()
    
    if not campaigns:
        return "Bu ay için tanımlı kampanya bulunmuyor."
    
    summary_parts = []
    for campaign_info in campaigns.values():
        summary_parts.append(f"• {campaign_info['description']}")
    
    return "Bu ayın aktif kampanyaları:\n" + "\n".join(summary_parts)

def update_campaigns(new_month: str, new_campaigns: Dict):
    """Yeni ay kampanyalarını güncelle (manuel olarak campaigns.py dosyasında yapılacak)"""
    print(f"Kampanyaları güncellemek için campaigns.py dosyasını manuel olarak düzenleyin.")
    print(f"Yeni ay: {new_month}")
    print(f"Yeni kampanyalar: {new_campaigns}")
