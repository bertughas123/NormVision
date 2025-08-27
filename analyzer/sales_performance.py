import pandas as pd
import os
import numpy as np
import json
from pathlib import Path


def create_monthly_sales_by_material_dataframe():
    """
    Musteri_Ciro_Raporu.xlsx dosyasından ay ay ciroları malzeme tipine göre ayıran DataFrame döndürür
    
    Returns:
        pandas.DataFrame: Malzeme tiplerine göre aylık ciro verileri (HEDEF)
    """
    # Excel dosyasının yolunu belirle
    excel_path = r"c:\Users\acer\Desktop\NORM HOLDING\datasforfinalblock\Musteri_Ciro_Raporu.xlsx"
    
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


def create_gerceklestirilen_satis_miktari():
    """
    Hedef DataFrame'den %18-%22 arası düşürülmüş değerlerle gerçekleştirilen satış miktarı DataFrame'i oluşturur
    
    Returns:
        pandas.DataFrame: Gerçekleştirilen Satış Miktarı
    """
    # Hedef DataFrame'i al
    hedef_df = get_hedef_dataframe()
    
    # Reproducible results için
    np.random.seed(42)
    
    # %18-%22 arası rastgele düşüş oranları matrisi oluştur
    decrease_rates = np.random.uniform(0.18, 0.22, size=hedef_df.shape)
    
    # Değerleri float'a çevirip düşürme işlemini uygula
    gerceklestirilen_df = hedef_df.astype(float) * (1 - decrease_rates)
    
    # Yuvarlayarak integer'a çevir
    gerceklestirilen_df = gerceklestirilen_df.round().astype(int)
    
    return gerceklestirilen_df


def compare_hedef_vs_gerceklestirilen():
    """
    Hedef ve gerçekleştirilen satış miktarlarını ay ay karşılaştırır
    
    Returns:
        dict: Karşılaştırma sonuçları
    """
    hedef_df = get_hedef_dataframe()
    gerceklestirilen_df = create_gerceklestirilen_satis_miktari()
    
    # Fark DataFrame'i (Mutlak)
    fark_df = hedef_df.subtract(gerceklestirilen_df, fill_value=0)
    
    # Yüzdelik fark DataFrame'i
    with np.errstate(divide='ignore', invalid='ignore'):
        yuzdelik_fark_df = hedef_df.divide(hedef_df, fill_value=0).subtract(
            gerceklestirilen_df.divide(hedef_df, fill_value=0), fill_value=0
        ).multiply(100).round(2)
        # NaN ve inf değerlerini 0 ile değiştir
        yuzdelik_fark_df = yuzdelik_fark_df.replace([np.inf, -np.inf, np.nan], 0)
    
    # Büyüme/Küçülme oranı (Gerçekleştirilen - Hedef) / Hedef * 100
    with np.errstate(divide='ignore', invalid='ignore'):
        buyume_orani_df = gerceklestirilen_df.subtract(hedef_df, fill_value=0).divide(
            hedef_df, fill_value=0
        ).multiply(100).round(2)
        # NaN ve inf değerlerini 0 ile değiştir  
        buyume_orani_df = buyume_orani_df.replace([np.inf, -np.inf, np.nan], 0)
    
    comparison_data = {
        'hedef': hedef_df,
        'gerceklestirilen': gerceklestirilen_df,
        'mutlak_fark': fark_df,
        'yuzdelik_fark': yuzdelik_fark_df,
        'buyume_orani': buyume_orani_df  # Negatif = küçülme, pozitif = büyüme
    }
    
    return comparison_data


def create_llm_input_data(comparison_data=None):
    """
    LLM modeline input verilecek formatta veri hazırlar
    
    Args:
        comparison_data: Önceden hesaplanmış karşılaştırma verisi (performans için)
    
    Returns:
        dict: LLM için hazırlanmış veri
    """
    if comparison_data is None:
        comparison_data = compare_hedef_vs_gerceklestirilen()
    
    # LLM input formatı
    llm_input = {
        "rapor_tipi": "Satış Hedef vs Gerçekleşen Analizi",
        "malzeme_tipleri": list(comparison_data['hedef'].index),
        "aylar": list(comparison_data['hedef'].columns),
        
        # Her ay için ayrı analiz
        "aylik_analiz": {},
        
        # Malzeme tipi bazında toplam analiz
        "malzeme_bazinda_analiz": {},
        
        # Genel özet
        "genel_ozet": {}
    }
    
    # Her ay için detaylı analiz
    for ay in comparison_data['hedef'].columns:
        # Güvenli toplam hesaplama ve büyüme oranı formatı
        toplam_hedef = comparison_data['hedef'][ay].sum()
        toplam_gerceklestirilen = comparison_data['gerceklestirilen'][ay].sum()
        
        # Genel büyüme oranını formatla
        genel_buyume = round(float((toplam_gerceklestirilen - toplam_hedef) / toplam_hedef * 100), 2) if toplam_hedef != 0 else 0.0
        if genel_buyume > 0:
            genel_buyume_str = f"+{genel_buyume}%"
        elif genel_buyume < 0:
            genel_buyume_str = f"{genel_buyume}%"  # Zaten - işareti var
        else:
            genel_buyume_str = "0.0%"
        
        ay_data = {
            "ay_adi": ay,
            "toplam_hedef": int(toplam_hedef) if pd.notna(toplam_hedef) else 0,
            "toplam_gerceklestirilen": int(toplam_gerceklestirilen) if pd.notna(toplam_gerceklestirilen) else 0,
            "toplam_fark": int(comparison_data['mutlak_fark'][ay].sum()) if pd.notna(comparison_data['mutlak_fark'][ay].sum()) else 0,
            "yuzdelik_fark": genel_buyume_str,
            "malzeme_detaylari": {}
        }
        
        # Bu ay için her malzeme tipinin detayları
        for malzeme_tipi in comparison_data['hedef'].index:
            try:
                hedef_val = comparison_data['hedef'].loc[malzeme_tipi, ay]
                gercek_val = comparison_data['gerceklestirilen'].loc[malzeme_tipi, ay]
                fark_val = comparison_data['mutlak_fark'].loc[malzeme_tipi, ay]
                yuzde_val = comparison_data['yuzdelik_fark'].loc[malzeme_tipi, ay]
                buyume_val = comparison_data['buyume_orani'].loc[malzeme_tipi, ay]
                
                # Büyüme oranını + veya - işaretiyle formatla
                buyume_formatted = round(float(buyume_val), 2) if pd.notna(buyume_val) else 0.0
                if buyume_formatted > 0:
                    buyume_str = f"+{buyume_formatted}%"
                elif buyume_formatted < 0:
                    buyume_str = f"{buyume_formatted}%"  # Zaten - işareti var
                else:
                    buyume_str = "0.0%"
                
                ay_data["malzeme_detaylari"][malzeme_tipi] = {
                    "hedef": int(hedef_val) if pd.notna(hedef_val) else 0,
                    "gerceklestirilen": int(gercek_val) if pd.notna(gercek_val) else 0,
                    "mutlak_fark": int(fark_val) if pd.notna(fark_val) else 0,
                    "yuzdelik_fark": buyume_str
                }
            except (ValueError, TypeError, KeyError):
                ay_data["malzeme_detaylari"][malzeme_tipi] = {
                    "hedef": 0,
                    "gerceklestirilen": 0,
                    "mutlak_fark": 0,
                    "yuzdelik_fark": "0.0%"
                }
        
        llm_input["aylik_analiz"][ay] = ay_data
    
    # Malzeme tipi bazında toplam analiz
    for malzeme_tipi in comparison_data['hedef'].index:
        # Güvenli toplam hesaplama ve büyüme oranı formatı
        toplam_hedef = comparison_data['hedef'].loc[malzeme_tipi].sum()
        toplam_gerceklestirilen = comparison_data['gerceklestirilen'].loc[malzeme_tipi].sum()
        
        # Genel büyüme oranını formatla
        genel_buyume = round(float((toplam_gerceklestirilen - toplam_hedef) / toplam_hedef * 100), 2) if toplam_hedef != 0 else 0.0
        if genel_buyume > 0:
            genel_buyume_str = f"+{genel_buyume}%"
        elif genel_buyume < 0:
            genel_buyume_str = f"{genel_buyume}%"  # Zaten - işareti var
        else:
            genel_buyume_str = "0.0%"
        
        malzeme_data = {
            "malzeme_tipi": malzeme_tipi,
            "toplam_hedef": int(toplam_hedef) if pd.notna(toplam_hedef) else 0,
            "toplam_gerceklestirilen": int(toplam_gerceklestirilen) if pd.notna(toplam_gerceklestirilen) else 0,
            "toplam_fark": int(comparison_data['mutlak_fark'].loc[malzeme_tipi].sum()) if pd.notna(comparison_data['mutlak_fark'].loc[malzeme_tipi].sum()) else 0,
            "yuzdelik_fark": genel_buyume_str,
            "aylik_detaylar": {}
        }
        
        # Bu malzeme tipi için her ayın detayları
        for ay in comparison_data['hedef'].columns:
            try:
                hedef_val = comparison_data['hedef'].loc[malzeme_tipi, ay]
                gercek_val = comparison_data['gerceklestirilen'].loc[malzeme_tipi, ay]
                fark_val = comparison_data['mutlak_fark'].loc[malzeme_tipi, ay]
                yuzde_val = comparison_data['yuzdelik_fark'].loc[malzeme_tipi, ay]
                buyume_val = comparison_data['buyume_orani'].loc[malzeme_tipi, ay]
                
                # Büyüme oranını + veya - işaretiyle formatla
                buyume_formatted = round(float(buyume_val), 2) if pd.notna(buyume_val) else 0.0
                if buyume_formatted > 0:
                    buyume_str = f"+{buyume_formatted}%"
                elif buyume_formatted < 0:
                    buyume_str = f"{buyume_formatted}%"  # Zaten - işareti var
                else:
                    buyume_str = "0.0%"
                
                malzeme_data["aylik_detaylar"][ay] = {
                    "hedef": int(hedef_val) if pd.notna(hedef_val) else 0,
                    "gerceklestirilen": int(gercek_val) if pd.notna(gercek_val) else 0,
                    "mutlak_fark": int(fark_val) if pd.notna(fark_val) else 0,
                    "yuzdelik_fark": buyume_str
                }
            except (ValueError, TypeError, KeyError):
                malzeme_data["aylik_detaylar"][ay] = {
                    "hedef": 0,
                    "gerceklestirilen": 0,
                    "mutlak_fark": 0,
                    "yuzdelik_fark": "0.0%"
                }
        
        llm_input["malzeme_bazinda_analiz"][malzeme_tipi] = malzeme_data
    
    # Genel özet istatistikleri
    toplam_tum_hedef = comparison_data['hedef'].sum().sum()
    toplam_tum_gerceklestirilen = comparison_data['gerceklestirilen'].sum().sum()
    
    # Genel büyüme oranını formatla
    genel_buyume = round(float((toplam_tum_gerceklestirilen - toplam_tum_hedef) / toplam_tum_hedef * 100), 2) if toplam_tum_hedef != 0 else 0.0
    if genel_buyume > 0:
        genel_buyume_str = f"+{genel_buyume}%"
    elif genel_buyume < 0:
        genel_buyume_str = f"{genel_buyume}%"  # Zaten - işareti var
    else:
        genel_buyume_str = "0.0%"
    
    llm_input["genel_ozet"] = {
        "toplam_hedef": int(toplam_tum_hedef) if pd.notna(toplam_tum_hedef) else 0,
        "toplam_gerceklestirilen": int(toplam_tum_gerceklestirilen) if pd.notna(toplam_tum_gerceklestirilen) else 0,
        "yuzdelik_fark": genel_buyume_str,
        "en_buyuyen_malzeme": "",
        "en_kucusen_malzeme": "",
        "aylara_gore_performans": {}
    }
    
    # En büyüyen/küçüsen malzeme tipleri
    buyume_oranlari = {}
    for malzeme_tipi in comparison_data['hedef'].index:
        toplam_hedef_m = comparison_data['hedef'].loc[malzeme_tipi].sum()
        toplam_gerceklestirilen_m = comparison_data['gerceklestirilen'].loc[malzeme_tipi].sum()
        if toplam_hedef_m != 0:
            buyume = (toplam_gerceklestirilen_m - toplam_hedef_m) / toplam_hedef_m * 100
            buyume_oranlari[malzeme_tipi] = buyume
    
    if buyume_oranlari:
        en_buyuyen = max(buyume_oranlari.keys(), key=lambda x: buyume_oranlari[x])
        en_kucusen = min(buyume_oranlari.keys(), key=lambda x: buyume_oranlari[x])
        
        llm_input["genel_ozet"]["en_buyuyen_malzeme"] = en_buyuyen
        llm_input["genel_ozet"]["en_kucusen_malzeme"] = en_kucusen
    
    # Aylara göre performans
    for ay in comparison_data['hedef'].columns:
        ay_hedef = comparison_data['hedef'][ay].sum()
        ay_gerceklestirilen = comparison_data['gerceklestirilen'][ay].sum()
        ay_buyume = round(float((ay_gerceklestirilen - ay_hedef) / ay_hedef * 100), 2) if ay_hedef != 0 else 0.0
        llm_input["genel_ozet"]["aylara_gore_performans"][ay] = {
            "hedef": int(ay_hedef) if pd.notna(ay_hedef) else 0,
            "gerceklestirilen": int(ay_gerceklestirilen) if pd.notna(ay_gerceklestirilen) else 0,
            "buyume_orani": ay_buyume
        }
    
    return llm_input


def save_analysis_to_files():
    """
    Analiz sonuçlarını dosyalara kaydet
    """
    # Hesapları tek seferlik yap
    comparison_data = compare_hedef_vs_gerceklestirilen()
    llm_data = create_llm_input_data(comparison_data)
    
    base_path = r"c:\Users\acer\Desktop\NORM HOLDING\datasforfinalblock"
    
    # Klasörü garanti oluştur
    Path(base_path).mkdir(parents=True, exist_ok=True)
    
    # Excel dosyalarını kaydet - kısa sheet adları ve index etiketleri ile
    excel_file_path = os.path.join(base_path, "Satis_Analizi_Detay.xlsx")
    with pd.ExcelWriter(excel_file_path) as writer:
        comparison_data['hedef'].to_excel(writer, sheet_name='Hedef', index=True, index_label='Malzeme Tipi')
        comparison_data['gerceklestirilen'].to_excel(writer, sheet_name='Gerceklesen', index=True, index_label='Malzeme Tipi')
        comparison_data['mutlak_fark'].to_excel(writer, sheet_name='Mutlak_Fark', index=True, index_label='Malzeme Tipi')
        comparison_data['yuzdelik_fark'].to_excel(writer, sheet_name='Yuzde_Fark', index=True, index_label='Malzeme Tipi')
        comparison_data['buyume_orani'].to_excel(writer, sheet_name='Buyume_Orani', index=True, index_label='Malzeme Tipi')
    
    # LLM input JSON olarak kaydet
    llm_json_path = os.path.join(base_path, "LLM_Input_Satis_Analizi.json")
    with open(llm_json_path, 'w', encoding='utf-8') as f:
        json.dump(llm_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Excel detay dosyası kaydedildi: {excel_file_path}")
    print(f"✅ LLM Input JSON kaydedildi: {llm_json_path}")
    
    return comparison_data, llm_data


# Test için fonksiyonları çalıştır
if __name__ == "__main__":
    print("=== NORM HOLDING SATIŞ ANALİZ RAPORU ===")
    print()
    
    print("📊 HEDEF DATAFRAME ÖZETİ")
    hedef_df = get_hedef_dataframe()
    print(f"Shape: {hedef_df.shape} (Malzeme Tipi × Ay)")
    print(f"Toplam Hedef Satış: {hedef_df.sum().sum():,}")
    print("İlk 3 satır:")
    print(hedef_df.head(3).to_string())
    print()
    
    print("🎯 GERÇEKLEŞTİRİLEN SATIŞ MİKTARI")
    gerceklestirilen_df = create_gerceklestirilen_satis_miktari()
    print(f"Shape: {gerceklestirilen_df.shape}")
    print(f"Toplam Gerçekleştirilen: {gerceklestirilen_df.sum().sum():,}")
    print("Örnek azalma (ilk malzeme için):")
    ilk_malzeme = hedef_df.index[0]
    ilk_ay = hedef_df.columns[0]
    hedef_val = float(hedef_df.loc[ilk_malzeme, ilk_ay])
    gercek_val = float(gerceklestirilen_df.loc[ilk_malzeme, ilk_ay])
    azalma_orani = (hedef_val - gercek_val) / hedef_val * 100
    print(f"{ilk_malzeme} {ilk_ay}: {hedef_val:,.0f} → {gercek_val:,.0f} (-%{azalma_orani:.1f})")
    print()
    
    print("📈 KARŞILAŞTIRMA ANALİZİ")
    comparison_data = compare_hedef_vs_gerceklestirilen()
    print("Genel Büyüme Oranları (%) - İlk 3 malzeme:")
    print(comparison_data['buyume_orani'].head(3).to_string())
    print()
    
    print("💾 DOSYALARI KAYDEDİYOR...")
    comparison_data, llm_data = save_analysis_to_files()
    print()
    
    print("🤖 LLM INPUT ÖRNEĞİ")
    print("Genel Özet:")
    print(f"- Toplam Hedef: {llm_data['genel_ozet']['toplam_hedef']:,}")
    print(f"- Toplam Gerçekleştirilen: {llm_data['genel_ozet']['toplam_gerceklestirilen']:,}")
    print(f"- Yüzdelik Fark: {llm_data['genel_ozet']['yuzdelik_fark']}")
    print(f"- En Büyüyen Malzeme: {llm_data['genel_ozet']['en_buyuyen_malzeme']}")
    print(f"- En Küçülen Malzeme: {llm_data['genel_ozet']['en_kucusen_malzeme']}")
    print()
    
    print("📅 AY BAZLI ÖRNEĞİ (Ağustos)")
    if 'Ağustos' in llm_data['aylik_analiz']:
        agustos_data = llm_data['aylik_analiz']['Ağustos']
        print(f"- Hedef: {agustos_data['toplam_hedef']:,}")
        print(f"- Gerçekleştirilen: {agustos_data['toplam_gerceklestirilen']:,}")
        print(f"- Yüzdelik Fark: {agustos_data['yuzdelik_fark']}")
    print()
    
    print("🏭 MALZEME BAZLI ÖRNEĞİ (İlk Malzeme)")
    ilk_malzeme_key = list(llm_data['malzeme_bazinda_analiz'].keys())[0]
    malzeme_data = llm_data['malzeme_bazinda_analiz'][ilk_malzeme_key]
    print(f"- Malzeme: {malzeme_data['malzeme_tipi']}")
    print(f"- Toplam Hedef: {malzeme_data['toplam_hedef']:,}")
    print(f"- Toplam Gerçekleştirilen: {malzeme_data['toplam_gerceklestirilen']:,}")
    print(f"- Yüzdelik Fark: {malzeme_data['yuzdelik_fark']}")
    print()
    
    print("✅ BAŞARIYLA TAMAMLANDI!")
    print("📁 Dosya Konumları:")
    print("  - Excel: datasforfinalblock/Satis_Analizi_Detay.xlsx")
    print("  - JSON: datasforfinalblock/LLM_Input_Satis_Analizi.json")
    print()
    print("🔍 JSON Kullanım Örnekleri (ASCII key'ler):")
    print("  - Belirli bir ay: data['aylik_analiz']['Ağustos']")
    print("  - Belirli bir malzeme: data['malzeme_bazinda_analiz']['Cıvata Ürün']")
    print("  - Ay-Malzeme kesişimi: data['aylik_analiz']['Ağustos']['malzeme_detaylari']['Cıvata Ürün']")
    print("  - Malzeme-Ay kesişimi: data['malzeme_bazinda_analiz']['Cıvata Ürün']['aylik_detaylar']['Ağustos']")

