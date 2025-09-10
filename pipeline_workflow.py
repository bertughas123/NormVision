#!/usr/bin/env python3
"""
Norm Holding Dynamic Summarizer - Complete Pipeline Workflow
============================================================

Bu modül tüm sistemi baştan sona otomatik çalıştırır:
1. runner_monthly.py - PDF analizi ve KPI JSON oluşturma
2. sales_performance.py - Excel analizi ve satış JSON oluşturma  
3. financial_analysis.py - Finansal zenginleştirme
4. final_assembler.py - Final rapor birleştirme

ÖNEMLI: Seçilen ay parametresi tüm modüllerde tutarlı kullanılır.

Author: System Designer
Date: 2025-09-09
"""

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

# Ana dizin referansı
BASE_DIR = Path(__file__).parent
PROJECT_ROOT = Path(r"C:\Users\acer\Desktop\NORM HOLDING")

class PipelineWorkflow:
    """Tüm sistemi baştan sona çalıştıran pipeline sınıfı"""
    
    def __init__(self, month: int, year: int = 2025, company_name: Optional[str] = None):
        """
        Args:
            month: Hedef ay (1-12, ZORUNLU)
            year: Hedef yıl (varsayılan: 2025)
            company_name: Şirket adı (opsiyonel, otomatik tespit edilir)
        """
        self.month = month
        self.year = year
        self.company_name = company_name
        self.start_time = time.time()
        
        # Ay isimlerini tanımla
        self.month_names = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
            7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
        }
        
        self.month_name = self.month_names.get(month, f"Ay{month}")
        
        # Sonuçları takip et
        self.results = {
            "runner_monthly": {"success": False, "duration": 0, "message": ""},
            "sales_performance": {"success": False, "duration": 0, "message": ""},
            "financial_analysis": {"success": False, "duration": 0, "message": ""},
            "final_assembler": {"success": False, "duration": 0, "message": ""}
        }
        
        print(f"\n{'='*80}")
        print(f"[START] NORM HOLDING PIPELINE WORKFLOW BAŞLATILIYOR")
        print(f"{'='*80}")
        print(f"[DATE] Hedef Dönem: {self.month_name} {self.year} (Ay: {self.month})")
        print(f"[COMPANY] Şirket: {self.company_name or 'Otomatik Tespit'}")
        print(f"[TIME] Başlangıç: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
    
    def _run_command(self, step_name: str, command: list, cwd: str = None) -> bool:
        """Alt işlem çalıştır ve sonucu kaydet"""
        step_start = time.time()
        
        print(f"\n[STEP] ADIM {len([r for r in self.results.values() if r['success']]) + 1}: {step_name.upper()}")
        print(f"[TOOL] Komut: {' '.join(command)}")
        print(f"[FOLDER] Dizin: {cwd or 'Mevcut'}")
        print("-" * 60)
        
        try:
            # UTF-8 encoding ile environment ayarla
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            
            # Komutu çalıştır
            result = subprocess.run(
                command,
                cwd=cwd or BASE_DIR,
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                timeout=600  # 10 dakika timeout (LLM işlemleri için)
            )
            
            duration = time.time() - step_start
            
            if result.returncode == 0:
                self.results[step_name]["success"] = True
                self.results[step_name]["message"] = "Başarılı"
                print(f"[SUCCESS] {step_name} BAŞARILI ({duration:.1f}s)")
                
                # Çıktıyı göster (son 200 karakter)
                if result.stdout:
                    output_preview = result.stdout.strip()[-200:]
                    print(f"[OUTPUT] Çıktı: ...{output_preview}")
                
            else:
                self.results[step_name]["success"] = False
                self.results[step_name]["message"] = f"Hata (kod: {result.returncode})"
                print(f"[ERROR] {step_name} BAŞARISIZ ({duration:.1f}s)")
                print(f"[FAILED] STDERR: {result.stderr.strip()}")
                print(f"[OUTPUT] STDOUT: {result.stdout.strip()}")
                
                return False
                
            self.results[step_name]["duration"] = duration
            return True
            
        except subprocess.TimeoutExpired:
            duration = time.time() - step_start
            self.results[step_name]["success"] = False
            self.results[step_name]["duration"] = duration
            self.results[step_name]["message"] = "Timeout (5 dakika)"
            print(f"[TIMER] {step_name} TIMEOUT ({duration:.1f}s)")
            return False
            
        except Exception as e:
            duration = time.time() - step_start
            self.results[step_name]["success"] = False
            self.results[step_name]["duration"] = duration
            self.results[step_name]["message"] = f"Exception: {str(e)}"
            print(f"[FAILED] {step_name} EXCEPTION ({duration:.1f}s): {e}")
            return False
    
    def step1_runner_monthly(self) -> bool:
        """Adım 1: PDF analizi ve KPI JSON oluşturma"""
        
        # PDF klasörü otomatik tespit
        pdf_dirs = [
            PROJECT_ROOT / "crmyapayzekamodlrnekdataset" / "pdfs",
            PROJECT_ROOT / "PDFs",
            PROJECT_ROOT / "Documents",
            BASE_DIR / "pdfs"
        ]
        
        pdf_dir = None
        for pd in pdf_dirs:
            if pd.exists() and any(pd.glob("*.pdf")):
                pdf_dir = str(pd)
                break
        
        if not pdf_dir:
            print(f"[ERROR] PDF klasörü bulunamadı. Kontrol edilen yerler:")
            for pd in pdf_dirs:
                print(f"   - {pd}")
            return False
        
        command = [
            sys.executable, "runners/runner_monthly.py",
            "--input-dir", pdf_dir,
            "--month", str(self.month),
            "--year", str(self.year),
            "--output-dir", str(BASE_DIR.parent),  # NORM HOLDING ana dizini
            "--llm"
        ]
        
        return self._run_command("runner_monthly", command)
    
    def step2_sales_performance(self) -> bool:
        """Adım 2: Excel analizi ve satış JSON oluşturma"""
        
        command = [
            sys.executable, "-m", "analyzer.sales_performance"
        ]
        
        return self._run_command("sales_performance", command)
    
    def step3_financial_analysis(self) -> bool:
        """Adım 3: Finansal zenginleştirme"""
        
        command = [
            sys.executable, "-m", "analyzer.financial_analysis"
        ]
        
        return self._run_command("financial_analysis", command)
    
    def step4_final_assembler(self) -> bool:
        """Adım 4: Final rapor birleştirme (AY PARAMETRESİ TUTARLI)"""
        
        # Python kodu olarak çalıştır (ay parametresi ile)
        try:
            step_start = time.time()
            
            print(f"\n[STEP] ADIM 4: FINAL_ASSEMBLER")
            print(f"[TOOL] Ay Parametresi: {self.month} ({self.month_name})")
            print(f"[COMPANY] Şirket: {self.company_name or 'Otomatik Tespit'}")
            print("-" * 60)
            
            # Final assembler modülünü import et
            sys.path.append(str(BASE_DIR))
            from bridge.final_assembler import run_complete_final_assembly
            
            # Ay parametresi ile çalıştır (TUTARLI!)
            final_report, success = run_complete_final_assembly(
                month=self.month,  # 👈 AYNI AY PARAMETRESİ
                year=self.year,
                company_name=self.company_name,
                base_directory=str(BASE_DIR)  # 👈 Project dizinini ilet
            )
            
            duration = time.time() - step_start
            
            if success and final_report:
                self.results["final_assembler"]["success"] = True
                self.results["final_assembler"]["message"] = "Başarılı"
                print(f"[SUCCESS] final_assembler BAŞARILI ({duration:.1f}s)")
                print(f"[STATS] Müşteri: {final_report.get('musteri_adi', 'N/A')}")
                print(f"[STATS] Rapor Bölümleri: {len(final_report.keys())}")
                
                if 'bridge_analizi' in final_report:
                    bridge = final_report['bridge_analizi']
                    print(f"[STATS] İlgilenilen Ürünler: {len(bridge.get('ilgilenilen_urun_gruplari', []))}")
                    print(f"[STATS] Teklif Verilen Ürünler: {len(bridge.get('teklif_verilen_urun_gruplari', []))}")
                
            else:
                self.results["final_assembler"]["success"] = False 
                self.results["final_assembler"]["message"] = "Final rapor oluşturulamadı"
                print(f"[ERROR] final_assembler BAŞARISIZ ({duration:.1f}s)")
                
            self.results["final_assembler"]["duration"] = duration
            return success
            
        except Exception as e:
            duration = time.time() - step_start if 'step_start' in locals() else 0
            self.results["final_assembler"]["success"] = False
            self.results["final_assembler"]["duration"] = duration
            self.results["final_assembler"]["message"] = f"Exception: {str(e)}"
            print(f"[FAILED] final_assembler EXCEPTION ({duration:.1f}s): {e}")
            return False
    
    def run_complete_pipeline(self) -> bool:
        """Tüm pipeline'ı baştan sona çalıştır"""
        
        steps = [
            ("1️⃣ PDF Analizi", self.step1_runner_monthly),
            ("2️⃣ Satış Analizi", self.step2_sales_performance), 
            ("3️⃣ Finansal Analiz", self.step3_financial_analysis),
            ("4️⃣ Final Birleştirme", self.step4_final_assembler)
        ]
        
        overall_success = True
        
        for step_desc, step_func in steps:
            print(f"\n[PROCESS] {step_desc} başlatılıyor...")
            
            step_success = step_func()
            
            if not step_success:
                print(f"\n[WARNING] {step_desc} başarısız oldu. Pipeline durduruluyor.")
                overall_success = False
                break
            
            print(f"[SUCCESS] {step_desc} tamamlandı.")
            
            # Adımlar arası kısa bekleme
            time.sleep(1)
        
        # Sonuç raporu
        self._print_final_report(overall_success)
        
        return overall_success
    
    def _print_final_report(self, overall_success: bool):
        """Pipeline sonuç raporunu yazdır"""
        
        total_duration = time.time() - self.start_time
        
        print(f"\n{'='*80}")
        print(f"[STATS] PIPELINE SONUÇ RAPORU")
        print(f"{'='*80}")
        print(f"[DATE] Dönem: {self.month_name} {self.year}")
        print(f"[TIMER] Toplam Süre: {total_duration:.1f} saniye")
        print(f"[RESULT] Genel Sonuç: {'[SUCCESS] BAŞARILI' if overall_success else '[ERROR] BAŞARISIZ'}")
        print(f"-" * 80)
        
        for step_name, result in self.results.items():
            status = "[SUCCESS]" if result["success"] else "[ERROR]"
            print(f"{status} {step_name.replace('_', ' ').title():20} | "
                  f"{result['duration']:6.1f}s | {result['message']}")
        
        print(f"{'='*80}")
        
        if overall_success:
            print(f"🎉 Pipeline başarıyla tamamlandı!")
            print(f"[FOLDER] Sonuç dosyaları:")
            print(f"   - KPI JSON: Reports/Monthly/{{şirket}}/{self.month:02d}-{self.month_name}/")
            print(f"   - Satış JSON: datasforfinalblock/LLM_Input_Satis_Analizi.json")
            print(f"   - Final Rapor: datasforfinalblock/{{şirket}}/Final_Report_*.json")
        else:
            print(f"[FAILED] Pipeline başarısız oldu. Yukarıdaki hataları kontrol edin.")
        
        print(f"{'='*80}\n")


def main():
    """Ana terminal arayüzü"""
    
    parser = argparse.ArgumentParser(
        description="Norm Holding Dynamic Summarizer - Complete Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
KULLANIM ÖRNEKLERİ:
  python pipeline_workflow.py --month 9                    # Eylül ayı için
  python pipeline_workflow.py --month 7 --year 2025       # Temmuz 2025 için
  python pipeline_workflow.py --month 8 --company "Şirinler Bağlantı Elem"

ADIMLAR:
  1. runner_monthly.py    - PDF analizi ve KPI JSON
  2. sales_performance.py - Excel analizi ve satış JSON  
  3. financial_analysis.py - Finansal zenginleştirme
  4. final_assembler.py   - Final rapor birleştirme
        """
    )
    
    parser.add_argument(
        "--month", "-m", 
        type=int, 
        required=True,
        choices=range(1, 13),
        help="Hedef ay (1-12, ZORUNLU)"
    )
    
    parser.add_argument(
        "--year", "-y",
        type=int,
        default=2025,
        help="Hedef yıl (varsayılan: 2025)"
    )
    
    parser.add_argument(
        "--company", "-c",
        type=str,
        help="Şirket adı (opsiyonel, otomatik tespit edilir)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Sadece parametreleri göster, çalıştırma"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        print(f"[DEBUG] DRY RUN MODU")
        print(f"[DATE] Ay: {args.month}")
        print(f"[DATE] Yıl: {args.year}")
        print(f"[COMPANY] Şirket: {args.company or 'Otomatik tespit'}")
        print(f"[START] Pipeline çalıştır: python pipeline_workflow.py --month {args.month}")
        return
    
    # Ana pipeline'ı başlat
    pipeline = PipelineWorkflow(
        month=args.month,
        year=args.year,
        company_name=args.company
    )
    
    success = pipeline.run_complete_pipeline()
    
    # Exit code ayarla
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
