"""
Final Assembler Module - Norm Holding Dynamic Summarizer
========================================================

Bu modül, zenginleştirilmiş satış/finansal analiz JSON'unu ve aylık KPI JSON'unu birleştirerek
tek bir kapsamlı final rapor oluşturur. Ayrıca satılan ürünler ile kampanyalarda sunulan ürünler
arasındaki kesişimleri bulmak için LLM tabanlı analiz yapar.

Workflow:
1. Zenginleştirilmiş satış/finansal verileri yükle (LLM_Input_Satis_Analizi.json)
2. KPI kampanya verilerini yükle (NormVision_KPI_...json)  
3. Ürün grupları arasında LLM analizi yap
4. Tüm veri kaynaklarını tek bir Final_Report.json'da birleştir

System Designer: Bertug
Date: 2025
"""

import os
import json
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.company_name_utils import normalize_company_name
import time
import glob
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from difflib import SequenceMatcher # for fuzzy matching because fuzzywuzzy is deprecated

# .env dosyasını yükle
load_dotenv()

# Mevcut KPI Bridge fonksiyonlarını import et
from .sales_visit_bridge import KPIBridge

class FinalAssembler:
    """Satış/Finansal analiz ve KPI verilerini birleştiren final assembler sınıfı"""
    
    def __init__(self, base_directory: str = None):
        """
        Args:
            base_directory: Projenin ana dizini (varsayılan: env'den DATAS_BASE)
        """
        # .env'den standart path'leri al
        self.reports_base = os.getenv('REPORTS_BASE', r"C:\Users\acer\Desktop\NORM HOLDING\project\NormHoldingDynamicSummarizer\Reports\Monthly")
        self.datas_base = os.getenv('DATAS_BASE', r"C:\Users\acer\Desktop\NORM HOLDING\datasforfinalblock")
        
        # Geriye uyumluluk için base_directory'yi de sakla
        self.base_directory = base_directory or os.path.dirname(self.datas_base)
        
        self.sales_financial_data = {}
        self.kpi_data = {}
        self.bridge_analysis = {}
        self.company_name = None  # Şirket adını saklamak için
        
    def load_sales_financial_data(self, file_path: str = None) -> bool:
        """
        Zenginleştirilmiş satış/finansal analiz verilerini yükle
        
        Args:
            file_path: JSON dosyasının yolu (varsayılan: otomatik)
            
        Returns:
            bool: Yükleme başarı durumu
        """
        if not file_path:
            file_path = os.path.join(self.datas_base, "LLM_Input_Satis_Analizi.json")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.sales_financial_data = json.load(f)
            
            # Şirket adını belirle ve sakla (normalize edilmiş)
            raw_company_name = self.sales_financial_data.get('musteri_adi', 'N/A')
            self.company_name = normalize_company_name(raw_company_name)
            
            print(f"[SUCCESS] Satış/Finansal veriler yüklendi: {file_path}")
            print(f"   - Malzeme Analizi: {len(self.sales_financial_data.get('malzeme_analizi', {}))}")
            print(f"   - Müşteri Adı: {self.company_name}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Satış/Finansal veriler yüklenemedi: {str(e)}")
            self.sales_financial_data = {}
            return False
    
    def find_latest_kpi_file(self, company_name: str = None, month: int = None, year: int = None) -> Optional[str]:
        """
        En güncel KPI JSON dosyasını şirket adına göre bul
        
        Args:
            company_name: Şirket adı (ZORUNLU)
            month: Ay (1-12, ZORUNLU - ay filtresi uygulanır)
            year: Yıl (varsayılan: 2025)
            
        Returns:
            str: KPI dosyasının yolu veya None
        """
        # Şirket adı zorunlu!
        if not company_name or company_name.strip() == "":
            print(f"[ERROR] HATA: Şirket adı parametresi zorunludur!")
            return None
        
        # Ay parametresi zorunlu!
        if month is None:
            print(f"[ERROR] HATA: Ay parametresi zorunludur! (1-12 arası değer verilmelidir)")
            return None
            
        if not (1 <= month <= 12):
            print(f"[ERROR] HATA: Ay parametresi 1-12 arası olmalıdır! Verilen: {month}")
            return None
            
        if year is None:
            year = 2025
            
        # Standart Reports klasörünü kullan
        base_reports_dir = self.reports_base
        
        if not os.path.exists(base_reports_dir):
            print(f"[WARNING] Reports dizini bulunamadı: {base_reports_dir}")
            return None
        
        # Şirket klasörünü fuzzy matching ile bul
        safe_company_name = self._sanitize_company_name(company_name)
        
        # Mevcut klasörleri listele
        try:
            available_folders = [d for d in os.listdir(base_reports_dir) 
                               if os.path.isdir(os.path.join(base_reports_dir, d))]
        except Exception as e:
            print(f"[ERROR] Reports klasörü okunamadı: {e}")
            return None
        
        # Önce tam eşleşme dene
        company_reports_dir = os.path.join(base_reports_dir, safe_company_name)
        if os.path.exists(company_reports_dir):
            print(f"[SUCCESS] Tam eşleşme bulundu: {safe_company_name}")
        else:
            # Fuzzy matching ile en yakın klasörü bul
            best_match = self._find_best_matching_folder(company_name, available_folders)
            if best_match:
                safe_company_name = best_match
                company_reports_dir = os.path.join(base_reports_dir, best_match)
                print(f"[SUCCESS] Fuzzy match kullanılacak: {best_match}")
            else:
                print(f"[ERROR] HATA: Şirket '{company_name}' için uygun klasör bulunamadı")
                print(f"   Mevcut klasörler: {available_folders}")
                print(f"   Aranan normalize: {safe_company_name}")
                return None
        
        # Şirket klasörü altındaki tüm KPI JSON dosyalarını bul
        pattern = os.path.join(company_reports_dir, "**", "NormVision_KPI_*.json")
        kpi_files = glob.glob(pattern, recursive=True)
        
        if not kpi_files:
            print(f"[ERROR] HATA: Şirket '{company_name}' klasöründe hiç KPI dosyası bulunamadı")
            return None
        
        print(f"[DEBUG] Şirket '{company_name}' klasöründe {len(kpi_files)} KPI dosyası bulundu")
        
        # Ay filtresi uygula (zorunlu)
        month_names = {
            1: "ocak", 2: "subat", 3: "mart", 4: "nisan", 5: "mayis", 6: "haziran",
            7: "temmuz", 8: "agustos", 9: "eylul", 10: "ekim", 11: "kasim", 12: "aralik"
        }
        month_name = month_names.get(month, "").lower()
        month_pattern = f"{month:02d}-"
        
        filtered_files = []
        for file_path in kpi_files:
            if month_pattern in file_path or month_name in file_path.lower():
                filtered_files.append(file_path)
        
        if not filtered_files:
            print(f"[ERROR] HATA: Şirket '{company_name}' için {month:02d} numaralı ay ({month_name}) ile eşleşen KPI dosyası bulunamadı")
            print(f"   Mevcut dosyalar:")
            for f in kpi_files:
                print(f"   - {os.path.basename(f)}")
            return None
        
        print(f"[DEBUG] Ay filtresi uygulandı: {len(filtered_files)} dosya kaldı")
        
        # En güncel dosyayı seç
        latest_file = max(filtered_files, key=os.path.getctime)
        print(f"[DEBUG] Şirket '{company_name}' için seçilen KPI dosyası: {latest_file}")
        return latest_file
    
    def _sanitize_company_name(self, company_name: str) -> str:
        """Şirket adını dosya adı için güvenli formata çevirir - Ortak normalizasyon kullanır"""
        return normalize_company_name(company_name)
    
    def _find_best_matching_folder(self, target_company: str, available_folders: List[str]) -> Optional[str]:
        """
        Fuzzy matching ile en yakın klasör adını bulur
        
        Args:
            target_company: Aranan şirket adı
            available_folders: Mevcut klasör adları listesi
            
        Returns:
            En yakın eşleşen klasör adı veya None
        """
        if not available_folders:
            return None
            
        best_match = None
        best_score = 0.0
        min_similarity = 0.7  # %70 benzerlik minimum
        
        # Normalize edilmiş target
        normalized_target = normalize_company_name(target_company)
        
        print(f"[DEBUG] Fuzzy matching - Target: '{normalized_target}'")
        print(f"[DEBUG] Available folders: {available_folders}")
        
        for folder in available_folders:
            # Her iki ismi de basitleştir
            folder_clean = folder.upper().replace('_', '').replace('.', '').replace('-', '')
            target_clean = normalized_target.upper().replace('_', '').replace('.', '').replace('-', '')
            
            # Benzerlik skorunu hesapla
            similarity = SequenceMatcher(None, target_clean, folder_clean).ratio()
            
            print(f"[DEBUG] '{folder}' -> similarity: {similarity:.3f}")
            
            if similarity > best_score and similarity >= min_similarity:
                best_score = similarity
                best_match = folder
        
        if best_match:
            print(f"[SUCCESS] Fuzzy match bulundu: '{best_match}' (skor: {best_score:.3f})")
        else:
            print(f"[WARNING] Yeterli benzerlikte klasör bulunamadı (min: {min_similarity})")
            
        return best_match
    
    def load_kpi_data(self, file_path: str = None, month: int = None, year: int = None) -> bool:
        """
        KPI analiz verilerini yükle
        
        Args:
            file_path: KPI JSON dosyasının yolu (varsayılan: otomatik tespit)
            month: Ay (1-12, ZORUNLU eğer file_path verilmemişse)
            year: Yıl (varsayılan: 2025)
            
        Returns:
            bool: Yükleme başarı durumu
        """
        if not file_path:
            # Şirket adını ve ayı kullanarak KPI dosyasını bul (her ikisi de zorunlu!)
            if month is None:
                print(f"[ERROR] HATA: KPI dosyası otomatik tespit edilirken ay parametresi zorunludur!")
                return False
                
            if not self.company_name or self.company_name.strip() == "":
                print(f"[ERROR] HATA: KPI dosyası otomatik tespit edilirken şirket adı zorunludur!")
                print(f"   Önce load_sales_financial_data() ile şirket adını yükleyin veya manuel file_path verin")
                return False
                
            file_path = self.find_latest_kpi_file(company_name=self.company_name, month=month, year=year)
            if not file_path:
                return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.kpi_data = json.load(f)
            
            campaigns = self.kpi_data.get("sunulan_urunler_ve_kampanyalar", [])
            print(f"[SUCCESS] KPI verileri yüklendi: {file_path}")
            print(f"   - Toplam Ziyaret: {self.kpi_data.get('toplam_ziyaret', 0)}")
            print(f"   - Sunulan Kampanya: {len(campaigns)}")
            return True
            
        except Exception as e:
            print(f"[ERROR] KPI verileri yüklenemedi: {str(e)}")
            self.kpi_data = {}
            return False
    
    def perform_llm_product_analysis(self) -> Dict[str, Any]:
        """
        Müşterinin satın aldığı ürünler ile KPI kampanyalarındaki ürünleri LLM ile karşılaştır
        
        Returns:
            Dict: Bridge analiz sonuçları
        """
        print(f"\n[DEBUG] LLM tabanlı ürün kesişim analizi başlatılıyor...")
        
        # Müşterinin satın aldığı ürün grupları (malzeme_analizi key'lerinden)
        customer_materials = list(self.sales_financial_data.get("malzeme_analizi", {}).keys())
        
        # KPI kampanyalarındaki sunulan ürünler
        kpi_campaigns = self.kpi_data.get("sunulan_urunler_ve_kampanyalar", [])
        
        if not customer_materials:
            print("[WARNING] Müşteri ürün bilgisi bulunamadı")
            return self._get_empty_analysis()
        
        if not kpi_campaigns:
            print("[WARNING] KPI kampanya bilgisi bulunamadı")
            return self._get_empty_analysis()
        
        # Mevcut KPIBridge sınıfını kullanarak analizi yap
        return self._use_existing_kpi_bridge_analysis(customer_materials, kpi_campaigns)
    
    def _use_existing_kpi_bridge_analysis(self, customer_materials: List[str], kpi_campaigns: List[str]) -> Dict[str, Any]:
        """
        Mevcut KPIBridge sınıfındaki LLM analiz fonksiyonunu kullan
        
        Args:
            customer_materials: Müşterinin satın aldığı ürün grupları
            kpi_campaigns: KPI kampanyalarındaki sunulan ürünler
            
        Returns:
            Dict: Bridge analiz sonuçları
        """
        try:
            # KPIBridge instance'ı oluştur
            customer_name = self.sales_financial_data.get('musteri_adi', 'Final Assembly Müşterisi')
            bridge = KPIBridge(customer_name)
            
            # Customer materials'ı KPIBridge'e set et
            bridge.customer_materials = customer_materials
            
            # KPI campaigns'ı set et
            bridge.kpi_campaigns = kpi_campaigns
            
            # Mevcut analyze_kpi_campaigns fonksiyonunu kullan
            result = bridge.analyze_kpi_campaigns()
            
            # Analiz tarihini ekle (eğer yoksa)
            if 'analiz_tarihi' not in result:
                result['analiz_tarihi'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"[SUCCESS] KPIBridge analizi kullanılarak tamamlandı")
            return result
            
        except Exception as e:
            print(f"[ERROR] KPIBridge analizi hatası: {str(e)}")
            return self._get_empty_analysis()
    
    def _get_empty_analysis(self) -> Dict[str, Any]:
        """Boş analiz sonucu döndür"""
        customer_materials = list(self.sales_financial_data.get("malzeme_analizi", {}).keys())
        return {
            "ilgilenilen_urun_gruplari": customer_materials,
            "sunulan_urun_gruplari": [],
            "teklif_verilen_urun_gruplari": [],
            "analiz_tarihi": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "analiz_durumu": "Başarısız",
            "hata": "LLM analizi yapılamadı"
        }
    
    def assemble_final_report(self) -> Dict[str, Any]:
        """
        Tüm verileri birleştirerek final raporu oluştur
        
        Returns:
            Dict: Birleştirilmiş final rapor
        """
        print(f"\n🔗 Final rapor birleştiriliyor...")
        
        # Ana veri olarak satış/finansal analizi kullan
        final_report = self.sales_financial_data.copy()
        
        # KPI analizini ekle
        if self.kpi_data:
            final_report["kpi_analizi"] = self.kpi_data
        
        # Bridge analizini ekle
        if self.bridge_analysis:
            final_report["bridge_analizi"] = self.bridge_analysis
        
        # Metadata ekle
        final_report["final_report_metadata"] = {
            "olusturma_tarihi": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "rapor_versiyonu": "1.0",
            "veri_kaynaklari": {
                "satis_finansal": bool(self.sales_financial_data),
                "kpi_analizi": bool(self.kpi_data),
                "bridge_analizi": bool(self.bridge_analysis)
            }
        }
        
        print(f"[SUCCESS] Final rapor birleştirildi")
        print(f"   - Ana bölümler: {len(final_report.keys())}")
        
        return final_report
    
    def save_final_report(self, final_report: Dict[str, Any], output_path: str = None) -> bool:
        """
        Final raporu dosyaya kaydet
        
        Args:
            final_report: Birleştirilmiş rapor verisi
            output_path: Çıktı dosyası yolu (varsayılan: otomatik)
            
        Returns:
            bool: Kaydetme başarı durumu
        """
        if not output_path:
            # Şirket adını kullanarak klasör ve dosya adı oluştur
            if self.company_name:
                safe_company_name = self._sanitize_company_name(self.company_name)
                
                # Şirket klasörü oluştur
                company_folder = os.path.join(self.datas_base, safe_company_name)
                filename = f"Final_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                output_path = os.path.join(company_folder, filename)
            else:
                # Şirket adı yoksa ana klasöre kaydet
                filename = f"Final_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                output_path = os.path.join(self.datas_base, filename)
        
        try:
            # Klasörü garanti oluştur
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(final_report, f, ensure_ascii=False, indent=2)
            
            print(f"[SUCCESS] Final rapor kaydedildi: {output_path}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Final rapor kaydetme hatası: {str(e)}")
            return False
    



def run_complete_final_assembly(
    sales_financial_path: str = None,
    kpi_path: str = None,
    output_path: str = None,
    base_directory: str = None,
    company_name: str = None,  # Yeni parametre
    month: int = None,  # ZORUNLU: Hangi ay için rapor oluşturulacak (1-12)
    year: int = None   # Yıl parametresi (varsayılan: 2025)
) -> Tuple[Dict[str, Any], bool]:
    """
    Komple final assembly workflow'unu çalıştır
    
    Args:
        sales_financial_path: Satış/Finansal JSON dosyası yolu (opsiyonel)
        kpi_path: KPI JSON dosyası yolu (opsiyonel)
        output_path: Çıktı dosyası yolu (opsiyonel)
        base_directory: Ana dizin yolu (opsiyonel)
        company_name: Şirket adı (opsiyonel, finansal verilerden otomatik çıkarılır)
        month: Hangi ay için KPI analizi yapılacak (1-12, ZORUNLU eğer kpi_path verilmemişse)
        year: Yıl (varsayılan: 2025)
        
    Returns:
        tuple: (Final rapor dict, başarı durumu)
    """
    print(f"\n{'='*60}")
    print(f"[START] FINAL ASSEMBLY WORKFLOW BAŞLATILIYOR")
    print(f"{'='*60}")
    
    # Temel parametreler kontrolü (eğer KPI dosyası otomatik bulunacaksa)
    if not kpi_path:
        if month is None:
            print("[ERROR] HATA: KPI dosyası otomatik tespit için ay parametresi (month) zorunludur!")
            print("   Örnek kullanım: run_complete_final_assembly(month=9) # Eylül ayı için")
            return {}, False
        
        if not (1 <= month <= 12):
            print(f"[ERROR] HATA: Ay parametresi 1-12 arası olmalıdır! Verilen: {month}")
            return {}, False
    
    # Assembler instance'ı oluştur
    assembler = FinalAssembler(base_directory)
    
    # 1. Satış/Finansal verileri yükle
    if not assembler.load_sales_financial_data(sales_financial_path):
        print("[ERROR] Satış/Finansal veriler yüklenemedi")
        return {}, False
    
    # Şirket adı verilmemişse, finansal verilerden çıkarmayı dene ve normalize et
    if not company_name and assembler.sales_financial_data:
        raw_company_name = assembler.sales_financial_data.get('musteri_adi')
        company_name = normalize_company_name(raw_company_name)
        assembler.company_name = company_name
    elif company_name:
        # Manuel verilen şirket adını da normalize et
        assembler.company_name = normalize_company_name(company_name)
    
    # KPI dosyası otomatik bulunacaksa şirket adı kontrolü
    if not kpi_path:
        if not assembler.company_name or assembler.company_name.strip() == "":
            print("[ERROR] HATA: KPI dosyası otomatik tespit için şirket adı zorunludur!")
            print("   - Şirket adını company_name parametresi ile verin, VEYA")
            print("   - Satış/Finansal JSON'da 'musteri_adi' alanının dolu olduğundan emin olun")
            return {}, False
    
    # 2. KPI verilerini yükle (ay bilgisi ile birlikte)
    if not assembler.load_kpi_data(file_path=kpi_path, month=month, year=year):
        print("[ERROR] KPI verileri yüklenemedi")
        return {}, False
    
    # 3. LLM tabanlı ürün kesişim analizini yap
    assembler.bridge_analysis = assembler.perform_llm_product_analysis()
    
    # 4. Final raporu birleştir
    final_report = assembler.assemble_final_report()
    
    # 5. Final raporu kaydet
    save_success = assembler.save_final_report(final_report, output_path)
    
    if not save_success:
        print("[WARNING] Final rapor oluşturuldu ama kaydedilemedi")
    
    print(f"\n[SUCCESS] Final Assembly workflow tamamlandı")
    print(f"   - Satış/Finansal: ✓")
    print(f"   - KPI Analizi: ✓") 
    print(f"   - Bridge Analizi: ✓")
    print(f"   - Final Rapor Kaydedildi: {'✓' if save_success else '✗'}")
    print(f"{'='*60}\n")
    
    return final_report, save_success


# Test ve demo kodu
if __name__ == "__main__":
    print("=== FINAL ASSEMBLER TEST ===")
    
    # Test workflow'unu çalıştır (Eylül ayı için)
    final_report, success = run_complete_final_assembly(month=9)
    
    print(f"\n=== SONUÇLAR ===")
    print(f"Başarı: {'✓' if success else '✗'}")
    
    if final_report:
        print(f"\n=== FINAL RAPOR ÖZETİ ===")
        metadata = final_report.get('final_report_metadata', {})
        print(f"Rapor Tarihi: {metadata.get('olusturma_tarihi', 'N/A')}")
        print(f"Ana Bölümler: {list(final_report.keys())}")
        
        if 'bridge_analizi' in final_report:
            bridge = final_report['bridge_analizi']
            ilgilenilen = len(bridge.get('ilgilenilen_urun_gruplari', []))
            teklif_verilen = len(bridge.get('teklif_verilen_urun_gruplari', []))
            print(f"İlgilenilen Ürün Sayısı: {ilgilenilen}")
            print(f"Teklif Verilen Ürün Sayısı: {teklif_verilen}")
        
        import json
        print(f"\n=== JSON RAPOR (İlk 300 karakter) ===")
        json_str = json.dumps(final_report, indent=2, ensure_ascii=False)
        print(json_str[:300] + "..." if len(json_str) > 300 else json_str)
