import pandas as pd
import os
import numpy as np
import json
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()


def create_monthly_sales_by_material_dataframe():
    """
    Musteri_Ciro_Raporu.xlsx dosyasından ay ay ciroları malzeme tipine göre ayıran DataFrame döndürür
    
    Returns:
        pandas.DataFrame: Malzeme tiplerine göre aylık ciro verileri (HEDEF)
    """
    # Excel dosyasının yolunu belirle
    datas_base = os.getenv('DATAS_BASE', r"c:\Users\acer\Desktop\NORM HOLDING\datasforfinalblock")
    excel_path = os.path.join(datas_base, "Musteri_Ciro_Raporu.xlsx")
    
    # Excel dosyasını oku
    df = pd.read_excel(excel_path)
    
    # 'Total' satırını kaldır
    df_filtered = df[df['Malzeme Tipi'] != 'Total'].copy()
    
    # Malzeme Tipi sütunundaki başlangıçtaki noktaları temizle
    df_filtered['Malzeme Tipi'] = df_filtered['Malzeme Tipi'].str.lstrip('.')
    
    # Ay sütunlarını belirle
    month_columns = [col for col in df.columns if 'Ciro' in col]
    
    # DataFrame'i malzeme tipine göre şekillendir
    result_df = df_filtered.set_index('Malzeme Tipi')[month_columns]
    
    # Sütun isimlerini temizle
    result_df.columns = [col.replace(' 2025 Ciro', '') for col in result_df.columns]
    
    return result_df


def get_hedef_dataframe():
    """Hedef satış miktarları DataFrame'i döndürür"""
    return create_monthly_sales_by_material_dataframe()


def load_real_sales_data(month_name="Ağustos", year=2025):
    """
    Gerçek satış verilerini aylık Excel dosyalarından yükler
    
    Args:
        month_name (str): Ay adı (örn: "Ağustos")
        year (int): Yıl
    
    Returns:
        pandas.DataFrame: Gerçekleşen satış verileri (malzeme tipi index'li)
    
    Raises:
        FileNotFoundError: Veri dosyası bulunamazsa
        Exception: Veri okuma hatası durumunda
    """
    # Excel dosya yolunu dinamik oluştur
    datas_base = os.getenv('DATAS_BASE', r"c:\Users\acer\Desktop\NORM HOLDING\datasforfinalblock")
    excel_path = os.path.join(datas_base, f"Şirinler Bağlantı El. {month_name} Gerçekleşen .xlsx")
    
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Gerçek veri dosyası bulunamadı: {excel_path}")
    
    try:
        # Excel dosyasını oku
        df = pd.read_excel(excel_path)
        
        # Malzeme Tipi sütunundaki başlangıçtaki noktaları temizle
        df['Malzeme Tipi'] = df['Malzeme Tipi'].str.lstrip('.')
        
        # Ciro sütununu bul (dinamik)
        ciro_column = [col for col in df.columns if 'Ciro' in col][0]
        
        # DataFrame'i malzeme tipine göre şekillendir
        result_df = df.set_index('Malzeme Tipi')[ciro_column]
        result_df.name = month_name  # Sütun adını ay adı yap
        
        print(f"[SUCCESS] {month_name} gerçek satış verileri yüklendi: {len(result_df)} malzeme")
        return result_df.to_frame()
        
    except Exception as e:
        raise Exception(f"Gerçek veri yüklenirken hata: {e}")


def compare_hedef_vs_gerceklestirilen(month_name="Ağustos", year=2025):
    """
    Hedef ve gerçekleştirilen satış miktarlarını basit karşılaştırma
    
    Args:
        month_name (str): Ay adı
        year (int): Yıl
    
    Returns:
        dict: Basit karşılaştırma sonuçları
    """
    hedef_df = get_hedef_dataframe()
    gerceklestirilen_df = load_real_sales_data(month_name, year)
    
    # Sadece ay sütununu al (hedef DataFrame'den belirtilen ay)
    ay_column = month_name if month_name in hedef_df.columns else hedef_df.columns[0]
    hedef_ay = hedef_df[ay_column]
    
    # Gerçekleşen verideki ay sütununu al 
    gerceklesen_ay = gerceklestirilen_df.iloc[:, 0]  # İlk sütun
    
    # Malzeme bazında karşılaştırma
    malzeme_analizi = {}
    for malzeme in gerceklesen_ay.index:
        if malzeme in hedef_ay.index:
            hedef_val = float(hedef_ay.loc[malzeme])
            gercek_val = float(gerceklesen_ay.loc[malzeme])
            fark = gercek_val - hedef_val
            buyume_orani = (fark / hedef_val * 100) if hedef_val != 0 else 0
            
            malzeme_analizi[malzeme] = {
                'hedef': hedef_val,
                'gerceklesen': gercek_val,
                'fark': fark,
                'buyume_orani': round(buyume_orani, 2)
            }
    
    # Genel toplam
    toplam_hedef = sum([data['hedef'] for data in malzeme_analizi.values()])
    toplam_gerceklesen = sum([data['gerceklesen'] for data in malzeme_analizi.values()])
    toplam_fark = toplam_gerceklesen - toplam_hedef
    genel_buyume = (toplam_fark / toplam_hedef * 100) if toplam_hedef != 0 else 0
    
    # Eksik malzemeler
    hedef_malzemeler = set(hedef_ay.index)
    gercek_malzemeler = set(gerceklesen_ay.index)
    eksik_malzemeler = list(hedef_malzemeler - gercek_malzemeler)
    
    return {
        'ay': month_name,
        'yil': year,
        'genel_ozet': {
            'toplam_hedef': toplam_hedef,
            'toplam_gerceklesen': toplam_gerceklesen,
            'toplam_fark': toplam_fark,
            'genel_buyume_orani': round(genel_buyume, 2)
        },
        'malzeme_analizi': malzeme_analizi,
        'eksik_malzemeler': eksik_malzemeler
    }


def create_llm_input_data(comparison_data=None, month_name="Ağustos", year=2025):
    """
    Basit LLM input formatı
    
    Args:
        comparison_data: Karşılaştırma verisi
        month_name (str): Ay adı
        year (int): Yıl
    
    Returns:
        dict: Basit LLM input
    """
    if comparison_data is None:
        comparison_data = compare_hedef_vs_gerceklestirilen(month_name, year)
    
    return {
        "rapor_tipi": "Aylık Satış Analizi",
        "ay": comparison_data['ay'],
        "yil": comparison_data['yil'],
        "genel_ozet": comparison_data['genel_ozet'],
        "malzeme_analizi": comparison_data['malzeme_analizi'],
        "eksik_malzemeler": comparison_data['eksik_malzemeler']
    }


def save_analysis_to_files(month_name="Ağustos", year=2025):
    """
    Analiz sonuçlarını dosyalara kaydet
    
    Args:
        month_name (str): Ay adı
        year (int): Yıl
    """
    # Hesapları tek seferlik yap
    comparison_data = compare_hedef_vs_gerceklestirilen(month_name, year)
    llm_data = create_llm_input_data(comparison_data, month_name, year)
    
    base_path = os.getenv('DATAS_BASE', r"c:\Users\acer\Desktop\NORM HOLDING\datasforfinalblock")
    
    # Klasörü garanti oluştur
    Path(base_path).mkdir(parents=True, exist_ok=True)
    
    # JSON dosyası kaydet
    json_path = Path(base_path) / "LLM_Input_Satis_Analizi.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(llm_data, f, ensure_ascii=False, indent=2)
    
    print(f"[SUCCESS] JSON kaydedildi: {json_path}")
    
    # Excel dosyası oluştur
    excel_path = Path(base_path) / "Satis_Analizi_Detay.xlsx"
    
    # Genel özet
    genel_df = pd.DataFrame([comparison_data['genel_ozet']])
    
    # Malzeme analizi
    malzeme_df = pd.DataFrame.from_dict(comparison_data['malzeme_analizi'], orient='index')
    
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        genel_df.to_excel(writer, sheet_name='Genel Özet', index=False)
        malzeme_df.to_excel(writer, sheet_name='Malzeme Analizi', index=True)
        
        if comparison_data['eksik_malzemeler']:
            eksik_df = pd.DataFrame({'Eksik Malzemeler': comparison_data['eksik_malzemeler']})
            eksik_df.to_excel(writer, sheet_name='Eksik Malzemeler', index=False)
    
    print(f"[SUCCESS] Excel kaydedildi: {excel_path}")


if __name__ == "__main__":
    print("=== NORM HOLDING BASIT SATIŞ ANALİZİ ===")
    print()
    
    print("[STATS] HEDEF DATAFRAME ÖZETİ")
    hedef_df = get_hedef_dataframe()
    print(f"Shape: {hedef_df.shape} (Malzeme Tipi × Ay)")
    print(f"Toplam Hedef Satış: {hedef_df.sum().sum():,}")
    print("İlk 3 satır:")
    print(hedef_df.head(3).to_string())
    print()
    
    print("[RESULT] GERÇEKLEŞTİRİLEN SATIŞ MİKTARI - AĞUSTOS 2025")
    try:
        comparison_data = compare_hedef_vs_gerceklestirilen("Ağustos", 2025)
        print(f"[SUCCESS] Analiz tamamlandı!")
        print(f"[STEP] Genel Özet:")
        print(f"  - Toplam Hedef: {comparison_data['genel_ozet']['toplam_hedef']:,.2f}")
        print(f"  - Toplam Gerçekleşen: {comparison_data['genel_ozet']['toplam_gerceklesen']:,.2f}")
        print(f"  - Fark: {comparison_data['genel_ozet']['toplam_fark']:,.2f}")
        print(f"  - Büyüme Oranı: {comparison_data['genel_ozet']['genel_buyume_orani']:.2f}%")
        
        if comparison_data['eksik_malzemeler']:
            print(f"[WARNING] Eksik Malzemeler ({len(comparison_data['eksik_malzemeler'])} adet):")
            for malzeme in comparison_data['eksik_malzemeler']:
                print(f"   - {malzeme}")
        
        print(f"\n[DEBUG] Malzeme Bazında Analiz:")
        for malzeme, data in comparison_data['malzeme_analizi'].items():
            print(f"  {malzeme}: {data['buyume_orani']:+.1f}% ({data['gerceklesen']:,.0f} / {data['hedef']:,.0f})")
        
    except (FileNotFoundError, Exception) as e:
        print(f"[ERROR] Gerçek veri yüklenemedi: {e}")
        print("Lütfen Excel dosyasının doğru konumda olduğundan emin olun.")
        exit(1)
    print()
    
    print("💾 DOSYALARI KAYDEDİYOR...")
    save_analysis_to_files("Ağustos", 2025)
    print()
    
    print("[SUCCESS] BAŞARIYLA TAMAMLANDI!")
    print("📁 Dosya Konumları:")
    print("  - Excel: datasforfinalblock/Satis_Analizi_Detay.xlsx")
    print("  - JSON: datasforfinalblock/LLM_Input_Satis_Analizi.json")

