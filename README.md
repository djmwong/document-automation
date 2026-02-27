# Document Automation System

A web application that extracts data from passport and G-28 forms using computer vision, OCR, and NLP techniques, then automatically populates a target web form using browser automation.

## Features

- **Multi-format Support**: PDF and image files (JPEG, PNG)
- **Intelligent Extraction**: 
  - LLM Vision (GPT-4o) for robust passport extraction across different formats
  - MRZ parsing for machine-readable passport zones
  - PDF form field reading for fillable G-28 forms
  - OCR + regex pattern matching as fallback
- **Browser Automation**: Playwright-based form filling
- **Real-time Preview**: View and verify extracted data before form population
- **Session Management**: Upload documents in any order and combine data seamlessly

## Architecture

```
├── app.py                    # FastAPI web server
├── form_filler.py            # Playwright browser automation
├── models.py                 # Pydantic data models
├── extractors/
│   ├── passport_extractor.py # Multi-strategy passport extraction
│   ├── llm_passport_extractor.py  # OpenAI GPT-4 Vision
│   └── g28_extractor.py      # G-28 form extraction
└── templates/
    └── index.html            # Web interface
```

## Installation

### Quick Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install system dependencies (macOS)
brew install tesseract poppler

# Install Playwright browsers
playwright install chromium
```

### Configure API Key

For best passport extraction accuracy, configure OpenAI:

```bash
echo "OPENAI_API_KEY=your-key-here" > .env
```

## Usage

```bash
# Start the server
python app.py

# Open http://localhost:8000
```

### Workflow

1. Upload a passport image or PDF
2. Upload a G-28 form (PDF)
3. Review the extracted data in the preview panel
4. Click "Populate Form" to auto-fill the target web form

## Extraction Strategies

### Passport Extraction

| Priority | Method | Description |
|----------|--------|-------------|
| 1 | LLM Vision | GPT-4o analyzes passport image for all fields |
| 2 | MRZ Parsing | Decodes machine-readable zone (ICAO Doc 9303) |
| 3 | OCR + Regex | Tesseract OCR with pattern matching fallback |

### G-28 Form Extraction

| Priority | Method | Description |
|----------|--------|-------------|
| 1 | PDF Form Fields | Reads fillable PDF form data directly |
| 2 | OCR + Regex | Image-based extraction with pattern matching |

## NLP Techniques

- **Pattern Matching**: Regex for structured fields (dates, phone numbers, emails, MRZ lines)
- **MRZ Decoding**: ICAO Doc 9303 standard machine-readable zone parsing
- **Date Normalization**: Flexible date format parsing and standardization
- **State Normalization**: Maps state names to 2-letter codes

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface |
| `/upload/passport` | POST | Upload and extract passport data |
| `/upload/g28` | POST | Upload and extract G-28 form data |
| `/extraction/{session_id}` | GET | Retrieve extracted data |
| `/fill-form-sync` | POST | Trigger form automation |

## Requirements

- Python 3.10+
- Tesseract OCR
- Poppler (for PDF processing)
- OpenAI API key (recommended for best passport accuracy)
