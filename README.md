# NormVision

## Project Status
**Note:** NormVision is currently in the development phase. Features and functionality are subject to change.

## Overview
NormVision is an intelligent document analysis system developed for Norm Holding to process, analyze and extract key business insights from visit reports. The system uses natural language processing and machine learning to transform unstructured PDF documents into structured data and actionable intelligence.

## Key Features
- PDF document parsing and text extraction
- Automatic field extraction from visit reports
- Intelligent data completion using Gemini AI
- Campaign tracking and compliance monitoring
- Turnover trend analysis and comparison
- Visit summary generation with recommendations
- Batch processing capability for multiple documents
- Exports to CSV and formatted Markdown reports
- Company-based grouping and chronological ordering
- Automated KPI calculation (financial & sales) via analyzer modules
- Weekly and monthly summary generation
- CRM synchronization through the bridge layer

## Project Structure
```
NormVision/
│
├── extractor/                       # Core extraction modules (PDF & LLM)
│   ├── campaigns.py
│   ├── llm_fill.py
│   ├── normalize.py
│   ├── notlar_parser.py
│   ├── pdf_reader.py
│   ├── schema.py
│   └── sections.py
│
├── analyzer/                        # KPI & trend analysis
│   ├── financial_analysis.py
│   └── sales_performance.py
│
├── bridge/
│   └── sales_visit_bridge.py        # CRM integration helpers
│
├── runner_step1.py                  # Single document processor
├── runner_batch.py                  # Bulk processor
├── runner_weekly.py                 # Weekly aggregator
├── runner_monthly.py                # Monthly aggregator
│
├── Reports/                         # Auto-generated reports (Markdown/JSON)
├── batch_logs_*                     # Processing logs
├── .env.example                     # Environment template
└── README.md
```

## Installation
1. Clone the repository:
   ```
   git clone https://github.com/your-organization/normvision.git
   cd normvision
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv env
   # On Windows
   env\Scripts\activate
   # On Linux/Mac
   source env/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```
   cp .env.example .env
   # Edit .env file with your API keys and configuration
   ```

## Usage

### Single Document Processing
```
python runner_step1.py "path/to/pdf_file.pdf"
```

### Batch Processing
```
python runner_batch.py --input-dir "path/to/pdf_directory" --llm --markdown
```

Options:
- `--input-dir`: Directory containing PDF files to process
- `--llm`: Enable AI-powered field completion and summary generation
- `--markdown`: Generate formatted Markdown reports
- `--firm-filter "regex"`: Filter results by company name pattern
- `--output-dir`: Specify output directory (default: current directory)

### Weekly Summary Generation
```
python runner_weekly.py --week 29 --year 2025 --llm
```

### Monthly Summary Generation
```
python runner_monthly.py --month 07 --year 2025 --llm --markdown
```

## Configuration
The system requires the following environment variables:
- `GEMINI_API_KEY`: Google Gemini API key for AI features

## Dependencies
- Python 3.9+
- Google Generative AI
- PyMuPDF (fitz)
- pdfplumber
- pytesseract (optional, for OCR)
- Other dependencies listed in requirements.txt

## Future Development
- Dashboard integration
- Interactive visualization of visit trends
- Enhanced campaign effectiveness tracking
- Custom reporting templates

## License
Proprietary software developed for Norm Holding. All rights reserved.
