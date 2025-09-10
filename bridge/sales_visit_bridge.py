"""
KPI Bridge - Finansal analiz ve KPI verilerini birleştiren köprü modülü

Workflow (run_complete_bridge_workflow):
1. Finansal Analiz JSON → malzeme tiplerini oku
2. KPI JSON → sunulan ürün/kampanyaları oku  
3. LLM ile eşleştirme analizi yap
4. Sonuçları Finansal Analiz JSON'a "bridge_analizi" key'i ile yaz
"""

import os
import json
import time
from typing import Dict, List, Any
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

class KPIBridge:
    """Finansal analiz ve KPI verilerini birleştiren köprü sınıfı"""
    
    def __init__(self, customer_name: str):
        """
        Args:
            customer_name: Analiz edilecek müşteri adı
        """
        self.customer_name = customer_name
        self.customer_materials = []  # Finansal JSON'dan gelecek
        self.kpi_campaigns = []  # KPI JSON'dan gelecek kampanyalar
        
    def load_materials_from_finansal_json(self, finansal_json_path: str) -> bool:
        """
        Finansal Analiz JSON dosyasından malzeme tiplerini yükle
        
        Args:
            finansal_json_path: Finansal Analiz JSON dosyasının yolu
            
        Returns:
            bool: Yükleme başarı durumu
        """
        try:
            with open(finansal_json_path, 'r', encoding='utf-8') as f:
                finansal_data = json.load(f)
            
            # "malzeme_tipleri" key'ini al
            materials = finansal_data.get("malzeme_tipleri", [])
            
            if isinstance(materials, list):
                self.customer_materials = materials
                print(f"[SUCCESS] Finansal Analiz JSON'dan {len(self.customer_materials)} malzeme tipi yüklendi")
                return True
            else:
                self.customer_materials = []
                print("[WARNING] Finansal Analiz JSON'da malzeme tipleri bulunamadı")
                return False
                
        except Exception as e:
            print(f"[ERROR] Finansal Analiz JSON yüklenemedi: {str(e)}")
            self.customer_materials = []
            return False
    
    def load_kpi_campaigns_from_json(self, kpi_json_path: str) -> bool:
        """
        KPI JSON dosyasından sunulan ürünler ve kampanyaları yükle
        
        Args:
            kpi_json_path: KPI JSON dosyasının yolu
            
        Returns:
            bool: Yükleme başarı durumu
        """
        try:
            with open(kpi_json_path, 'r', encoding='utf-8') as f:
                kpi_data = json.load(f)
            
            # "sunulan_urunler_ve_kampanyalar" key'ini al
            campaigns = kpi_data.get("sunulan_urunler_ve_kampanyalar", [])
            
            if isinstance(campaigns, list):
                self.kpi_campaigns = campaigns
            else:
                self.kpi_campaigns = []
                
            print(f"[SUCCESS] KPI JSON'dan {len(self.kpi_campaigns)} kampanya yüklendi")
            return True
            
        except Exception as e:
            print(f"[ERROR] KPI JSON yüklenemedi: {str(e)}")
            self.kpi_campaigns = []
            return False
    
    def save_bridge_result_to_finansal_json(self, finansal_json_path: str, bridge_result: Dict[str, Any]) -> bool:
        """
        Bridge analiz sonuçlarını Finansal Analiz JSON'a ekle
        
        Args:
            finansal_json_path: Finansal Analiz JSON dosyasının yolu
            bridge_result: Bridge analiz sonuçları
            
        Returns:
            bool: Kaydetme başarı durumu
        """
        try:
            # Mevcut Finansal Analiz JSON'u oku
            with open(finansal_json_path, 'r', encoding='utf-8') as f:
                finansal_data = json.load(f)
            
            # Bridge analiz sonuçlarını ekle
            finansal_data["bridge_analizi"] = {
                "analiz_tarihi": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "ilgilenilen_urun_gruplari": bridge_result.get("ilgilenilen_urun_gruplari", []),
                "sunulan_urun_gruplari": bridge_result.get("sunulan_urun_gruplari", []),
                "teklif_verilen_urun_gruplari": bridge_result.get("teklif_verilen_urun_gruplari", [])
            }
            
            # Güncellenmiş veriyi geri yaz
            with open(finansal_json_path, 'w', encoding='utf-8') as f:
                json.dump(finansal_data, f, ensure_ascii=False, indent=2)
            
            print(f"[SUCCESS] Bridge analiz sonuçları Finansal Analiz JSON'a eklendi")
            return True
            
        except Exception as e:
            print(f"[ERROR] Finansal Analiz JSON'a yazma hatası: {str(e)}")
            return False
        
    def analyze_kpi_campaigns(self) -> Dict[str, Any]:
        """
        KPI JSON'daki kampanyalar ile müşterinin aldığı ürünleri karşılaştır
        
        Returns:
            Dict: Analiz sonuçları (İlgilenilen, Sunulan, Teklif Verilen ürün grupları)
        """
        print(f"\n[DEBUG] {self.customer_name} için KPI kampanya analizi yapılıyor...")
        
        # KPI kampanyaları var mı kontrol et
        if not self.kpi_campaigns:
            print("[WARNING] KPI JSON'da kampanya bilgisi bulunamadı")
            return self._get_empty_result()
        
        # KPI kampanyalarını string olarak birleştir
        campaigns_text = "\n".join(self.kpi_campaigns)
        
        # LLM ile analiz yap
        return self._llm_analysis(campaigns_text)
    
    def _llm_analysis(self, campaigns_text: str) -> Dict[str, Any]:
        """KPI kampanyaları için LLM analizi"""
        try:
            # Gemini API'yi yapılandır
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                print("[WARNING] GEMINI_API_KEY bulunamadı")
                return self._get_empty_result()
                
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            # Müşterinin aldığı ürünleri JSON formatında hazırla
            customer_materials_json = json.dumps(self.customer_materials, ensure_ascii=False)
            
            prompt = f"""
            Aşağıda bir müşterinin satın aldığı ürün grupları ve KPI raporundaki kampanya bilgileri var.
            
            MÜŞTERİNİN SATIN ALDIĞI ÜRÜN GRUPLARI (Finansal Analiz'den):
            {customer_materials_json}
            
            KPI RAPORUNDAKI KAMPANYALAR VE SUNULAN ÜRÜNLER:
            {campaigns_text}
            
            Görevin:
            1. "İlgilenilen Ürün Grupları": Müşterinin daha önce satın aldığı ürün grupları (yukarıdaki listeden)
            2. "Sunulan Ürün Grupları": KPI raporunda bahsedilen ürün grupları (kampanya detaylarından çıkar)
            3. "Teklif Verilen Ürün Grupları": Hem satın alınan hem de sunulan ürünlerin kesişimi
            
            ÖNEMLİ:
            - Kampanya detaylarından sadece ÜRÜN GRUPLARINI çıkar (fiyat, indirim, tonaj bilgilerini ALMA)
            - Ürün gruplarını normalize et (örn: "Paslanmaz", "Paslanmaz Çelik", "Inox" -> "Paslanmaz Çelik")
            - Sadece net olarak tanımlanabilen ürün gruplarını ekle
            - Genel kampanya isimlerini değil, spesifik ürün gruplarını al
            
            Cevabını JSON formatında ver:
            {{
                "ilgilenilen_urun_gruplari": ["liste"],
                "sunulan_urun_gruplari": ["liste"],  
                "teklif_verilen_urun_gruplari": ["liste"]
            }}
            """
            
            # Rate limiting
            time.sleep(2)
            
            response = model.generate_content(prompt)
            result_text = response.text.strip()
            
            # JSON'u parse et
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
            
            result = json.loads(result_text)
            
            # Debug bilgisi
            print(f"[SUCCESS] KPI Analizi tamamlandı:")
            print(f"   - İlgilenilen: {len(result.get('ilgilenilen_urun_gruplari', []))} ürün")
            print(f"   - Sunulan: {len(result.get('sunulan_urun_gruplari', []))} ürün")
            print(f"   - Teklif Verilen: {len(result.get('teklif_verilen_urun_gruplari', []))} ürün")
            
            return result
            
        except Exception as e:
            print(f"[ERROR] KPI LLM analizi hatası: {str(e)}")
            return self._get_empty_result()
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """Boş sonuç döndür"""
        return {
            "ilgilenilen_urun_gruplari": self.customer_materials.copy(),
            "sunulan_urun_gruplari": [],
            "teklif_verilen_urun_gruplari": [],
            "analiz_durumu": "Başarısız",
            "hata": "LLM analizi yapılamadı"
        }
    



def run_complete_kpi_workflow(
    finansal_json_path: str,
    kpi_json_path: str,
    customer_name: str = "Norm Holding Müşterisi"
) -> tuple[Dict[str, Any], bool]:
    """
    Komple KPI bridge workflow'u çalıştır:
    1. Finansal Analiz JSON'dan malzeme tiplerini oku
    2. KPI JSON'dan kampanyaları oku
    3. LLM ile analiz yap
    4. Sonuçları Finansal Analiz JSON'a geri yaz
    
    Args:
        finansal_json_path: Finansal Analiz JSON dosyasının yolu
        kpi_json_path: KPI JSON dosyasının yolu
        customer_name: Müşteri adı
        
    Returns:
        tuple: (JSON analiz sonucu, başarı durumu)
    """
    print(f"\n{'='*60}")
    print(f"🔗 KPI BRIDGE WORKFLOW BAŞLATILIYOR")
    print(f"{'='*60}")
    
    # Bridge instance'ı oluştur
    bridge = KPIBridge(customer_name)
    
    # 1. Finansal Analiz JSON'dan malzeme tiplerini yükle
    if not bridge.load_materials_from_finansal_json(finansal_json_path):
        print("[ERROR] Finansal Analiz JSON yüklenemedi")
        return bridge._get_empty_result(), False
    
    # 2. KPI JSON'dan kampanyaları yükle
    if not bridge.load_kpi_campaigns_from_json(kpi_json_path):
        print("[ERROR] KPI JSON yüklenemedi")
        return bridge._get_empty_result(), False
    
    # 3. Analizi yap
    analysis_result = bridge.analyze_kpi_campaigns()
    
    # 4. Sonuçları Finansal Analiz JSON'a geri yaz
    save_success = bridge.save_bridge_result_to_finansal_json(finansal_json_path, analysis_result)
    
    if not save_success:
        print("[WARNING] Analiz tamamlandı ama Finansal Analiz JSON'a yazılamadı")
    
    print(f"\n[SUCCESS] KPI Bridge workflow tamamlandı")
    print(f"   - Malzeme Tipleri: {len(bridge.customer_materials)}")
    print(f"   - KPI Kampanyaları: {len(bridge.kpi_campaigns)}")
    print(f"   - Finansal JSON Güncellendi: {'✓' if save_success else '✗'}")
    print(f"{'='*60}\n")
    
    return analysis_result, save_success


# Test kodu - Gerçek dosyalarla test
if __name__ == "__main__":
    import os
    
    # Ana dizine geç
    os.chdir("C:/Users/acer/Desktop/NORM HOLDING")
    
    print("=== GERÇEK DOSYALARLA KPI BRIDGE TEST ===")
    
    # Gerçek dosya yolları (yeni klasör yapısına göre)
    finansal_path = "datasforfinalblock/LLM_Input_Finansal_Analiz.json"
    kpi_path = "Reports/Monthly/Sirinler_Baglanti_Elem/07-Temmuz/NormVision_KPI_Sirinler_Baglanti_Elem_Temmuz_2025_20250829_005546.json"
    
    # Test et
    result, success = run_complete_kpi_workflow(
        finansal_json_path=finansal_path,
        kpi_json_path=kpi_path,
        customer_name="Şirinler Bağlantı Elem."
    )
    
    print(f"\n=== SONUÇLAR ===")
    print(f"Başarı: {'✓' if success else '✗'}")
    
    print(f"\n=== ANALİZ SONUCU ===")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
