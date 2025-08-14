import os, re, json, time  # Added time import
from typing import Dict, Any, List
from .normalize import parse_amount
from .campaigns import check_campaign_mentions, get_campaign_summary

# Minimum delay between API calls (seconds)
MIN_API_DELAY = 6

def _missing_fields(kv: Dict[str, Any], declared_keys: List[str]) -> List[str]:
    """Bu PDF'te declared olan ama kv'de eksik olan alanları döndür"""
    missing = []
    for key in declared_keys:
        # Para alanları için _value suffix'i kontrol et
        if key in ['ciro_2024', 'ciro_2025', 'q2_hedef', 'yaklasik_siparis_tutari']:
            if not kv.get(f"{key}_value"):
                missing.append(key)
        else:
            # Metin alanları için direkt kontrol
            if not kv.get(key) or kv.get(key) == "—":
                missing.append(key)
    return missing

# Track last API call timestamp
_last_api_call = 0

def _rate_limited_api_call(model, prompt):
    """API çağrılarını rate limit ile yap"""
    global _last_api_call
    
    # Calculate time since last API call
    current_time = time.time()
    elapsed = current_time - _last_api_call
    
    # If needed, wait to maintain minimum delay between calls
    if _last_api_call > 0 and elapsed < MIN_API_DELAY:
        wait_time = MIN_API_DELAY - elapsed
        print(f"🔍 DEBUG: Rate limit - waiting {wait_time:.2f}s before next API call")
        time.sleep(wait_time)
    
    # Make the API call
    response = model.generate_content(prompt)
    
    # Update timestamp after successful call
    _last_api_call = time.time()
    
    return response
    
def _extract_turnover_values(kv: Dict[str, Any]) -> tuple:
    """2024 ve 2025 ciro değerlerini çıkar"""
    try:
        ciro_2024 = kv.get('ciro_2024_value', 0) or 0
        ciro_2025 = kv.get('ciro_2025_value', 0) or 0
        
        # String ise float'a çevir
        if isinstance(ciro_2024, str):
            ciro_2024 = float(re.sub(r'[^\d.]', '', ciro_2024)) if ciro_2024 != "—" else 0
        if isinstance(ciro_2025, str):
            ciro_2025 = float(re.sub(r'[^\d.]', '', ciro_2025)) if ciro_2025 != "—" else 0
            
        return float(ciro_2024), float(ciro_2025)
    except:
        return 0, 0

def llm_fill_and_summarize(kv: Dict[str, Any], raw_notlar: str, declared_keys: List[str]) -> Dict[str, Any]:
    """PDF-spesifik dinamik alan doldurma"""
    
    print(f"🔍 DEBUG: Starting LLM fill...")
    print(f"🔍 DEBUG: declared_keys = {declared_keys}")
    print(f"🔍 DEBUG: API key exists = {bool(os.getenv('GEMINI_API_KEY'))}")
    
    # 👇 GENEL YORUM DEBUG 
    genel_yorum = kv.get('genel_yorum', '')
    print(f"🔍 DEBUG: Genel Yorum çekildi mi:")
    print(f"🔍 DEBUG: Uzunluk: {len(genel_yorum)} karakter")
    print(f"🔍 DEBUG: İlk 50 karakter: {genel_yorum[:50]}")
    print(f"🔍 DEBUG: Son 50 karakter: {genel_yorum[-50:] if len(genel_yorum) > 50 else genel_yorum}")
    print(f"🔍 DEBUG: Sonda 'girec' var mı: {'Evet' if 'girec' in genel_yorum[-10:] else 'Hayır'}")
    print(f"🔍 DEBUG: Sonda 'girecekler' var mı: {'Evet' if 'girecekler' in genel_yorum else 'Hayır'}")
    
    try:
        # Import kontrolü
        try:
            import google.generativeai as genai
            print("🔍 DEBUG: google.generativeai imported successfully")
        except ImportError as e:
            print(f"🔍 DEBUG: Import error: {e}")
            kv["ozet"] = "google.generativeai kütüphanesi yüklü değil"
            return kv
        
        # API key kontrolü
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("🔍 DEBUG: No API key found")
            kv["ozet"] = "GEMINI_API_KEY bulunamadı"
            return kv
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        print(f"🔍 DEBUG: Gemini model loaded successfully")

        # Declared boş değilse: KV-first mod (sadece declared alanları doldur)
        if declared_keys:
            missing = _missing_fields(kv, declared_keys)
            print(f"🔍 DEBUG: missing fields = {missing}")
            
            if missing:
                # Şema oluştur (sadece eksik alanlar için)
                schema_properties = {}
                for key in missing:
                    if key in ['ciro_2024', 'ciro_2025', 'q2_hedef', 'yaklasik_siparis_tutari']:
                        schema_properties[key] = {
                            "type": ["string", "null"],
                            "description": f"{key} (sayı + para birimi formatında)"
                        }
                    else:
                        field_descriptions = {
                            'gorusulen_kisi': 'görüşülen kişinin adı',
                            'pozisyon': 'görüşülen kişinin pozisyonu',
                            'sunulan_urun_gruplari_kampanyalar': 'sunulan ürün grupları veya kampanyalar',
                            'rakip_firma_sartlari': 'rakip firma şartları',
                            'siparis_alindi_mi': 'sipariş alınıp alınmadığı',
                            'siparis_alinamayan_urunler_ve_nedenleri': 'sipariş alınamayan ürünler ve nedenleri'
                        }
                        schema_properties[key] = {
                            "type": ["string", "null"],
                            "description": field_descriptions.get(key, key)
                        }

                # Genel yorumu öncelikle kullan, yoksa tüm metni
                source_text = kv.get('genel_yorum') or raw_notlar
                # 👇 SOURCE TEXT DEBUG
                print(f"🔍 DEBUG: Source Text içeriği (ilk 100 karakter): {source_text[:100]}")
                print(f"🔍 DEBUG: Source Text içeriği (son 50 karakter): {source_text[-50:] if len(source_text) > 50 else source_text}")
                
                prompt_kv = f"""
Aşağıdaki Türkçe metinden belirtilen alanları çıkar. 
Emin değilsen null bırak.

SADECE JSON formatında yanıt ver:
{json.dumps(schema_properties, indent=2, ensure_ascii=False)}

METIN:
{source_text}
""".strip()

                print(f"🔍 DEBUG: Sending LLM request for missing fields...")
                
                # Rate-limited API call
                resp = _rate_limited_api_call(model, prompt_kv)
                
                print(f"🔍 DEBUG: LLM response received: {resp.text[:200]}...")
                
                try:
                    # JSON temizleme
                    txt = (resp.text or "").strip()
                    txt = re.sub(r"^```json|```$", "", txt, flags=re.IGNORECASE|re.MULTILINE).strip()
                    filled = json.loads(txt)
                    print(f"🔍 DEBUG: Parsed JSON: {filled}")
                except Exception as e:
                    print(f"🔍 DEBUG: JSON parse error: {e}")
                    filled = {}

                # Para alanlarını özel olarak işle
                for key in missing:
                    if key in ['ciro_2024', 'ciro_2025', 'q2_hedef', 'yaklasik_siparis_tutari'] and filled.get(key):
                        dec, cur = parse_amount(str(filled[key]))
                        kv[f"{key}_value"] = dec  # setdefault() yerine direkt atama
                        kv[f"{key}_currency"] = cur
                        kv[f"{key}_raw"] = str(filled[key])
                        print(f"🔍 DEBUG: Set money field {key} = {dec} {cur}")
                    elif key in filled:
                        # None değeri yerine "—" kullan
                        value = filled[key] if filled[key] is not None else "—"
                        kv[key] = value  # Direkt atama
                        print(f"🔍 DEBUG: Set text field {key} = {value}")
            
            else:
                print(f"🔍 DEBUG: No missing fields, skipping LLM fill")

        # Her koşulda özet oluştur - Kampanya kontrolü ve ciro analizi ile
        print(f"🔍 DEBUG: Generating enhanced summary...")
        
        # Kampanya kontrolü
        campaign_checks = check_campaign_mentions(raw_notlar)
        campaign_warnings = []
        
        if campaign_checks:
            for campaign_key, campaign_info in campaign_checks.items():
                if isinstance(campaign_info, dict) and not campaign_info.get("mentioned", True):
                    campaign_warnings.append(f"• {campaign_info['name']} firma sahibine belirtilmemiş")
        
        # Ciro analizi
        ciro_2024, ciro_2025 = _extract_turnover_values(kv)
        
        # Aktif kampanyalar listesi
        current_campaigns = get_campaign_summary()
        
        prompt_sum = f"""
Bu ziyaret raporunu analiz et ve kapsamlı bir özet oluştur.

ZİYARET METNİ:
{raw_notlar}

KAMPANYA DURUMU:
{current_campaigns}

CİRO BİLGİLERİ:
2024 Ciro: {ciro_2024 if ciro_2024 > 0 else 'Belirtilmemiş'}
2025 Ciro: {ciro_2025 if ciro_2025 > 0 else 'Belirtilmemiş'}

GÖREVLER:
1. Ziyaret özetini yap (kim ile görüşüldü, amaç, sonuç) - 1-2 cümle
2. Ciro durumunu analiz et:
   - Eğer her iki ciro da varsa karşılaştır (arttı/azaldı/aynı ve yüzde kaç)
   - Sadece biri varsa durumu belirt
   - Hiçbiri yoksa "ciro bilgisi yok" de
3. Kampanya kontrolü yap:
   - Zımba Tabancası özel fiyat (1000 TL) belirtilmiş mi?
   - Vida ürünlerinde özel iskonto (%54) belirtilmiş mi?
   - Belirtilmemişse uyarı ver: "X kampanyası firma sahibine belirtilmemiş"
4. Bir sonraki ziyaret için öneri ver - 1 cümle

ÇIKTI FORMATI:
Normal paragraf şeklinde, akıcı ve kısa yaz. Numaralı liste kullanma.

KAMPANYA UYARILARI:
{'; '.join(campaign_warnings) if campaign_warnings else 'Kontrol edilecek'}
""".strip()

        # Rate-limited API call for summary
        resp_sum = _rate_limited_api_call(model, prompt_sum)
        summary = (resp_sum.text or "").strip()
        print(f"🔍 DEBUG: Enhanced summary generated: {summary[:100]}...")
        if summary:
            kv["ozet"] = summary

    except Exception as e:
        print(f"🔍 DEBUG: LLM error: {e}")
        import traceback
        traceback.print_exc()
        # LLM hatası durumunda sessizce devam et
        kv.setdefault("ozet", f"LLM hatası: {str(e)}")

    return kv
