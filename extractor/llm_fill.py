import os, re, json
from typing import Dict, Any, List
from .normalize import parse_amount

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
                
                resp = model.generate_content(prompt_kv)
                
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

        # Her koşulda özet oluştur - DAHA KISA ve AKICI prompt
        print(f"🔍 DEBUG: Generating summary...")
        prompt_sum = f"""
Bu ziyaret raporunu 2-3 AKICI cümleyle özetle.

SADECE SOMUT BİLGİLER:
- Kim ile görüşüldü + amaç
- Ne alındı/sipariş edildi (rakamlarla)
- Sonuç

Numaralı liste değil, normal paragraf yaz. Kısa ve net:

{raw_notlar}
""".strip()

        resp_sum = model.generate_content(prompt_sum)
        summary = (resp_sum.text or "").strip()
        print(f"🔍 DEBUG: Summary generated: {summary[:100]}...")
        if summary:
            kv["ozet"] = summary

    except Exception as e:
        print(f"🔍 DEBUG: LLM error: {e}")
        import traceback
        traceback.print_exc()
        # LLM hatası durumunda sessizce devam et
        kv.setdefault("ozet", f"LLM hatası: {str(e)}")

    return kv
