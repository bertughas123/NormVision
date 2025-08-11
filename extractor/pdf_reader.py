import pdfplumber
import re
import os
import tempfile
import subprocess
from pdfminer.layout import LAParams

def read_pdf_text(path: str) -> str:
    """
    PDF metin okuma (4 aşamalı) - chunks ile:
    1. pdfplumber (optimize LAParams)
    2. PyMuPDF (fitz) 
    3. pdftotext (xpdf-utils)
    4. OCR (pytesseract)
    """
    
    # 1️⃣ pdfplumber ile optimize extraction
    chunks = []
    try:
        # Optimize LAParams
        custom_laparams = LAParams(
            char_margin=1.0,
            line_margin=0.3,
            word_margin=0.1,
            boxes_flow=0.5,
            detect_vertical=True,
            all_texts=True
        )
        
        with pdfplumber.open(path) as pdf:
            print(f"[1] pdfplumber deneniyor... ({len(pdf.pages)} sayfa)")
            
            for i, page in enumerate(pdf.pages):
                try:
                    # LAParams ile extraction
                    text = page.extract_text(laparams=custom_laparams) or ""
                    if not text:
                        # Fallback - normal extraction
                        text = page.extract_text(
                            x_tolerance=5,
                            y_tolerance=8,
                            layout=False,
                            keep_blank_chars=True,
                            horizontal_ltr=True
                        ) or ""
                except (TypeError, Exception):
                    # Son fallback
                    text = page.extract_text() or ""
                
                chunks.append(text)
                
        full_text = "\n".join(chunks)
        
        # Kalite kontrolü
        if is_text_quality_good(full_text, len(chunks)):
            return clean_text(full_text)
            
    except Exception as e:
        print(f"[!] pdfplumber error: {e}")

    # 2️⃣ PyMuPDF fallback
    try:
        import fitz
        print("[2] PyMuPDF (fitz) deneniyor...")
        
        chunks = []
        doc = fitz.open(path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Daha iyi text extraction flags
            text = page.get_text("text", 
                               flags=fitz.TEXT_PRESERVE_LIGATURES | 
                                     fitz.TEXT_PRESERVE_WHITESPACE | 
                                     fitz.TEXT_DEHYPHENATE) or ""
            chunks.append(text)
            
        doc.close()
        full_text = "\n".join(chunks)
        
        if is_text_quality_good(full_text, len(chunks)):
            return clean_text(full_text)
            
    except ImportError:
        print("[!] PyMuPDF (fitz) yüklü değil - atlanıyor")
    except Exception as e:
        print(f"[!] PyMuPDF error: {e}")

    # 3️⃣ pdftotext fallback
    try:
        print("[3] pdftotext deneniyor...")
        
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp:
            temp_filename = temp.name

        subprocess.run(
            ["pdftotext", "-layout", path, temp_filename],
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )

        with open(temp_filename, "r", encoding="utf-8", errors="ignore") as f:
            full_text = f.read()
            
        # Cleanup
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            
        if is_text_quality_good(full_text, 1):  # pdftotext tüm sayfaları birleştirir
            return clean_text(full_text)
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[!] pdftotext bulunamadı - atlanıyor")
    except Exception as e:
        print(f"[!] pdftotext error: {e}")

    # 4️⃣ OCR fallback (son çare)
    try:
        import pytesseract
        from pdf2image import convert_from_path
        
        print("[4] OCR (pytesseract) deneniyor...")
        
        # PDF'i görüntülere çevir
        images = convert_from_path(path, dpi=300)
        chunks = []
        
        for i, img in enumerate(images):
            print(f"  Sayfa {i+1}/{len(images)} OCR yapılıyor...")
            text = pytesseract.image_to_string(img, lang="tur+eng")
            chunks.append(text)
            
        full_text = "\n".join(chunks)
        return clean_text(full_text)
        
    except ImportError:
        print("[!] OCR modülleri yüklü değil - atlanıyor")
    except Exception as e:
        print(f"[!] OCR error: {e}")

    # Hiçbiri çalışmazsa boş döndür
    print("[!] Tüm PDF okuma yöntemleri başarısız!")
    return ""

def is_text_quality_good(text: str, page_count: int) -> bool:
    """Metin kalitesini değerlendir - gelişmiş kriterler"""
    if not text or not text.strip():
        return False
    
    # Temel uzunluk kontrolü
    text_length = len(text.strip())
    if text_length < 50:
        return False
    
    # Sayfa başına ortalama karakter sayısı (daha akıllı eşik)
    avg_chars_per_page = text_length / max(page_count, 1)
    if avg_chars_per_page < 100:  # Çok az içerik
        return False
    
    # Türkçe karakterlerin varlığını kontrol et
    turkish_chars = sum(1 for c in text if c in "çğıöşüÇĞIİÖŞÜ")
    if turkish_chars > 0:  # Türkçe içerik varsa daha toleranslı ol
        return True
    
    # Rakam ve harf oranı kontrolü (çok fazla çöp karakter var mı?)
    alnum_chars = sum(1 for c in text if c.isalnum())
    if text_length > 0 and (alnum_chars / text_length) < 0.3:
        return False  # %30'dan az alfanumerik karakter = çöp
    
    # Bilinen kelime varlığı (PDF'lerde olması beklenen)
    known_words = ['ciro', 'hedef', 'firma', 'ziyaret', 'sipariş', 'görüşülen']
    found_words = sum(1 for word in known_words if word.lower() in text.lower())
    if found_words >= 2:  # En az 2 bilinen kelime varsa kabul et
        return True
    
    # Varsayılan: yeterli uzunluk varsa kabul et
    return avg_chars_per_page >= 200

def clean_text(text: str) -> str:
    """Metni temizle ve normalize et"""
    if not text:
        return ""
    
    # Fazla boşlukları temizle
    text = re.sub(r'\n{3,}', '\n\n', text)  # 3+ satır sonu -> 2
    text = re.sub(r'[ \t]{2,}', ' ', text)  # Çoklu boşluk/tab -> tek boşluk
    text = re.sub(r'[ \t]*\n[ \t]*', '\n', text)  # Satır sonlarındaki boşlukları temizle
    
    # PDF artifacts'ları temizle
    text = text.replace('\x0c', '')  # Form feed
    text = text.replace('\r', '\n')  # CR -> LF
    
    return text.strip()
