"""
Document Automation Web Application

FastAPI application for extracting data from passport and G-28 forms
and automatically populating web forms using browser automation.
"""
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.requests import Request
from pydantic import BaseModel

from models import ExtractedFormData, PassportData, AttorneyData
from extractors.passport_extractor import PassportExtractor
from extractors.g28_extractor import G28Extractor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Document Automation System", version="1.0.0")

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

passport_extractor = PassportExtractor()
g28_extractor = G28Extractor()
extraction_store: dict[str, ExtractedFormData] = {}


class ExtractionResponse(BaseModel):
    success: bool
    message: str
    session_id: str
    data: Optional[ExtractedFormData] = None


class FormFillerRequest(BaseModel):
    session_id: str
    target_url: str = "https://mendrika-alma.github.io/form-submission/"


class FormFillerResponse(BaseModel):
    success: bool
    message: str
    screenshot_path: Optional[str] = None


def generate_session_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload/passport", response_model=ExtractionResponse)
async def upload_passport(file: UploadFile = File(...), session_id: Optional[str] = None):
    """Upload and extract data from a passport document."""
    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png"}
    ext = Path(file.filename or "").suffix.lower()
    
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, JPEG, or PNG.")
    
    if not session_id:
        session_id = generate_session_id()
    
    try:
        content = await file.read()
        file_path = UPLOAD_DIR / f"passport_{session_id}{ext}"
        file_path.write_bytes(content)
        
        passport_data = passport_extractor.extract(file_path, content)
        
        if session_id not in extraction_store:
            extraction_store[session_id] = ExtractedFormData()
        extraction_store[session_id].passport = passport_data
        
        file_path.unlink(missing_ok=True)
        
        return ExtractionResponse(
            success=True,
            message=f"Passport extracted ({passport_data.extraction_method})",
            session_id=session_id,
            data=extraction_store[session_id]
        )
    except Exception as e:
        logger.error(f"Passport extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/g28", response_model=ExtractionResponse)
async def upload_g28(file: UploadFile = File(...), session_id: Optional[str] = None):
    """Upload and extract data from a G-28 form."""
    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png"}
    ext = Path(file.filename or "").suffix.lower()
    
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, JPEG, or PNG.")
    
    if not session_id:
        session_id = generate_session_id()
    
    try:
        content = await file.read()
        file_path = UPLOAD_DIR / f"g28_{session_id}{ext}"
        file_path.write_bytes(content)
        
        attorney_data, beneficiary_data = g28_extractor.extract(file_path, content)
        
        if session_id not in extraction_store:
            extraction_store[session_id] = ExtractedFormData()
        extraction_store[session_id].attorney = attorney_data
        
        # Merge beneficiary data into passport section
        if beneficiary_data:
            if extraction_store[session_id].passport:
                existing = extraction_store[session_id].passport
                if not existing.last_name:
                    existing.last_name = beneficiary_data.last_name
                if not existing.first_name:
                    existing.first_name = beneficiary_data.first_name
                if not existing.middle_name:
                    existing.middle_name = beneficiary_data.middle_name
            else:
                extraction_store[session_id].passport = beneficiary_data
        
        file_path.unlink(missing_ok=True)
        
        return ExtractionResponse(
            success=True,
            message=f"G-28 extracted ({attorney_data.extraction_method})",
            session_id=session_id,
            data=extraction_store[session_id]
        )
    except Exception as e:
        logger.error(f"G-28 extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/extraction/{session_id}", response_model=ExtractionResponse)
async def get_extraction(session_id: str):
    """Get extracted data for a session."""
    if session_id not in extraction_store:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return ExtractionResponse(
        success=True,
        message="Data retrieved",
        session_id=session_id,
        data=extraction_store[session_id]
    )


@app.post("/fill-form", response_model=FormFillerResponse)
async def fill_form(request: FormFillerRequest):
    """Fill the target form with extracted data using browser automation."""
    if request.session_id not in extraction_store:
        raise HTTPException(status_code=404, detail="Session not found")
    
    data = extraction_store[request.session_id]
    if not data.passport and not data.attorney:
        raise HTTPException(status_code=400, detail="No data available")
    
    try:
        from form_filler import FormFiller
        filler = FormFiller()
        screenshot_path = await filler.fill_form(data, request.target_url)
        
        return FormFillerResponse(
            success=True,
            message="Form filled successfully",
            screenshot_path=screenshot_path
        )
    except Exception as e:
        logger.error(f"Form filling failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/fill-form-sync")
async def fill_form_sync(request: FormFillerRequest):
    """Synchronous form filling - waits for completion."""
    if request.session_id not in extraction_store:
        raise HTTPException(status_code=404, detail="Session not found")
    
    data = extraction_store[request.session_id]
    if not data.passport and not data.attorney:
        return {"success": False, "error": "No data available"}
    
    try:
        from form_filler import FormFiller
        filler = FormFiller()
        screenshot_path = await filler.fill_form(data, request.target_url)
        return {"success": True, "message": "Form filled", "screenshot": screenshot_path}
    except Exception as e:
        logger.error(f"Form filling failed: {e}")
        return {"success": False, "error": str(e)}


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete session data."""
    if session_id in extraction_store:
        del extraction_store[session_id]
        return {"success": True}
    raise HTTPException(status_code=404, detail="Session not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
