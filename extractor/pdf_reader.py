import pdfplumber
import re
import subprocess
import os
import tempfile

def read_pdf_text(path: str) -> str:
    """Tüm sayfaları en güçlü yöntemlerle okuyup \n ile birleştir."""
    
    # Önce pdfplumber ile dene
    chunks = []
    try:
        with pdfplumber.open(path) as pdf:
            for p in pdf.pages:
                # Daha agresif parametreler
                t = p.extract_text(
                    x_tolerance=5,  # Daha yüksek
                    y_tolerance=8,  # Daha yüksek
                    layout=False,
                    keep_blank_chars=True,
                    use_text_flow=True,
                    horizontal_ltr=True
                ) or ""
                chunks.append(t)
        
        full_text = "\n".join(chunks)
    except Exception as e:
        print(f"pdfplumber error: {e}")
        full_text = ""
    
    # pdftotext kullanarak alternatif çözüm (daha güçlü)
    if "girec" in full_text and not "girecek" in full_text:
        try:
            # Geçici dosya oluştur
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp:
                temp_filename = temp.name
            
            # pdftotext kullan (xpdf-utils)
            subprocess.run(['pdftotext', '-layout', path, temp_filename], check=True)
            
            # Çıktıyı oku
            with open(temp_filename, 'r', encoding='utf-8') as f:
                full_text = f.read()
                
            # Geçici dosyayı sil
            os.remove(temp_filename)
        except Exception as e:
            print(f"pdftotext error: {e}")
    
    # Metin temizliği - çift boşlukları ve gereksiz satır sonlarını düzelt
    full_text = re.sub(r'\n{3,}', '\n\n', full_text)  # 3+ satır sonunu 2'ye indir
    
    return full_text
