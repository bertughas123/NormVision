# PDF Data Extraction Project

Bu proje, PDF dosyalarından veri çıkarma ve işleme işlemlerini gerçekleştirmek için tasarlanmıştır.

## Dosya Yapısı

```
project/
├── extractor/
│   ├── __init__.py
│   ├── pdf_reader.py      # PDF okuma işlemleri
│   ├── sections.py        # Bölüm ayırma işlemleri
│   ├── normalize.py       # Veri normalleştirme
│   ├── notlar_parser.py   # Notlar ayrıştırma
│   ├── schema.py          # Veri şeması tanımları
│   └── llm_fill.py        # LLM ile veri doldurma
├── runner.py              # Ana çalıştırma scripti
├── .env.example           # Çevre değişkenleri örneği
└── README.md              # Bu dosya
```

## Kurulum

1. Gerekli Python paketlerini yükleyin
2. `.env.example` dosyasını `.env` olarak kopyalayın ve gerekli değerleri doldurun
3. `runner.py` scriptini çalıştırın

## Kullanım

```bash
python runner.py
```
