import pdfplumber

def read_pdf_text(path: str) -> str:
    """Tüm sayfaları sırayla okuyup \n ile birleştir."""
    chunks = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            chunks.append(t)
    return "\n".join(chunks)
