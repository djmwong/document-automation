"""
G-28 form data extraction using PDF form fields and OCR fallback.
Extracts attorney/representative information from G-28 forms.
"""
import re
from pathlib import Path
from typing import Optional, Tuple
import logging

from models import AttorneyData, PassportData, normalize_state

logger = logging.getLogger(__name__)


class G28Extractor:
    """G-28 form extractor using PDF form fields with OCR fallback."""
    
    def extract(self, file_path: Path, file_bytes: Optional[bytes] = None) -> Tuple[AttorneyData, Optional[PassportData]]:
        """Extract attorney data from G-28 form."""
        #for fillable PDFs, extracting using PDF form fields
        if file_path.suffix.lower() == ".pdf":
            form_data, beneficiary = self._extract_pdf_form_fields(file_path, file_bytes)
            if form_data and self._calculate_confidence(form_data) > 0.3:
                form_data.extraction_method = "PDF_FORM_FIELDS"
                return form_data, beneficiary
        
        #fallback to OCR
        images = self._get_images(file_path, file_bytes)
        full_text = ""
        for img in images:
            text = self._ocr_image(img)
            if text:
                full_text += text + "\n"
        
        if full_text:
            data = self._extract_from_text(full_text)
            data.extraction_method = "OCR+NLP"
            data.confidence_score = self._calculate_confidence(data)
            return data, None
        
        return AttorneyData(extraction_method="FAILED", confidence_score=0.0), None
    
    def _extract_pdf_form_fields(self, file_path: Path, file_bytes: Optional[bytes] = None) -> Tuple[Optional[AttorneyData], Optional[PassportData]]:
        """Extract data from PDF form fields."""
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf") if file_bytes else fitz.open(str(file_path))
            
            form_fields = {}
            for page in doc:
                for widget in page.widgets():
                    if widget.field_name and widget.field_value:
                        form_fields[widget.field_name] = widget.field_value
                        form_fields[widget.field_name.lower()] = widget.field_value
            doc.close()
            
            if not form_fields:
                return None, None
            
            data = AttorneyData()
            beneficiary = PassportData()
            
            mappings = {
                'last_name': ['Pt1Line2a_FamilyName[0]'],
                'first_name': ['Pt1Line2b_GivenName[0]'],
                'middle_name': ['Pt1Line2c_MiddleName[0]'],
                'street_address': ['Line3a_StreetNumber[0]'],
                'apt_ste_flr': ['Line3b_AptSteFlrNumber[0]'],
                'city': ['Line3c_CityOrTown[0]'],
                'state': ['Line3d_State[0]'],
                'zip_code': ['Line3e_ZipCode[0]'],
                'country': ['Line3h_Country[0]'],
                'daytime_phone': ['Line4_DaytimeTelephoneNumber[0]'],
                'mobile_phone': ['Line7_MobileTelephoneNumber[0]'],
                'email': ['Line6_EMail[0]'],
                'bar_number': ['Pt2Line1b_BarNumber[0]'],
                'licensing_authority': ['Pt2Line1a_LicensingAuthority[0]'],
                'law_firm_name': ['Pt2Line1d_NameofFirmOrOrganization[0]'],
            }
            
            for attr, field_names in mappings.items():
                for name in field_names:
                    for key in [name, name.lower()]:
                        if key in form_fields:
                            value = form_fields[key]
                            if value and value.strip() and value.strip().upper() != 'N/A':
                                setattr(data, attr, value.strip())
                                break
            
            #email in wrong field
            if data.mobile_phone and '@' in data.mobile_phone:
                if not data.email:
                    data.email = data.mobile_phone
                data.mobile_phone = None
            
            beneficiary_mappings = {
                'last_name': ['Pt3Line5a_FamilyName[0]'],
                'first_name': ['Pt3Line5b_GivenName[0]'],
                'middle_name': ['Pt3Line5c_MiddleName[0]'],
            }
            
            for attr, field_names in beneficiary_mappings.items():
                for name in field_names:
                    for key in [name, name.lower()]:
                        if key in form_fields:
                            value = form_fields[key]
                            if value and value.strip() and value.strip().upper() != 'N/A':
                                setattr(beneficiary, attr, value.strip())
                                break
            
            if beneficiary.last_name or beneficiary.first_name:
                beneficiary.extraction_method = "G28_BENEFICIARY"
                beneficiary.confidence_score = 0.5
            else:
                beneficiary = None
            
            data.confidence_score = self._calculate_confidence(data)
            return data, beneficiary
            
        except Exception as e:
            logger.warning(f"PDF form field extraction failed: {e}")
            return None, None
    
    def _get_images(self, file_path: Path, file_bytes: Optional[bytes] = None) -> list:
        """Convert document to PIL Images."""
        from PIL import Image
        import io
        
        try:
            if file_path.suffix.lower() == ".pdf":
                from pdf2image import convert_from_path, convert_from_bytes
                return convert_from_bytes(file_bytes, dpi=300) if file_bytes else convert_from_path(str(file_path), dpi=300)
            else:
                return [Image.open(io.BytesIO(file_bytes)) if file_bytes else Image.open(file_path)]
        except Exception as e:
            logger.error(f"Failed to load images: {e}")
            return []
    
    def _ocr_image(self, image) -> Optional[str]:
        """Run OCR on image."""
        try:
            import pytesseract
            return pytesseract.image_to_string(image, config='--psm 3')
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return None
    
    def _extract_from_text(self, text: str) -> AttorneyData:
        """extract attorney data using pattern matching"""
        data = AttorneyData()
        
        #name patterns
        name_patterns = [
            (r'(?:Family\s*Name|Last\s*Name)[^A-Za-z]*([A-Za-z][A-Za-z\-\']+)', 'last_name'),
            (r'(?:Given\s*Name|First\s*Name)[^A-Za-z]*([A-Za-z][A-Za-z\-\']+)', 'first_name'),
            (r'(?:Middle\s*Name)[^A-Za-z]*([A-Za-z][A-Za-z\-\']*)', 'middle_name'),
        ]
        for pattern, field in name_patterns:
            if not getattr(data, field):
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if value.lower() not in ('name', 'last', 'first', 'given', 'family', 'middle'):
                        setattr(data, field, value.title())
        
        #address patterns
        street_match = re.search(r'(?:Street|Address)[^A-Za-z0-9]*(\d+[^,\n]{5,50})', text, re.IGNORECASE)
        if street_match:
            data.street_address = re.sub(r'\s+', ' ', street_match.group(1).strip())[:100]
        
        city_match = re.search(r'(?:City|Town)[^A-Za-z]*([A-Z][A-Za-z\s]{2,30}?)(?:,|\s+[A-Z]{2}\s)', text)
        if city_match:
            data.city = re.sub(r'\s+[A-Z]{2}$', '', city_match.group(1).strip())
        
        state_match = re.search(r'(?:State)[^A-Za-z]*([A-Z]{2})\b', text)
        if state_match:
            data.state = normalize_state(state_match.group(1))
        
        zip_match = re.search(r'(?:ZIP|Postal)[^0-9]*(\d{5}(?:-\d{4})?)', text, re.IGNORECASE)
        if zip_match:
            data.zip_code = zip_match.group(1)
        
        #contact info
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            data.email = email_match.group(0).lower()
        
        #professional info
        bar_match = re.search(r'(?:Bar\s*Number)[^A-Za-z0-9]*([A-Z0-9]{4,12})', text, re.IGNORECASE)
        if bar_match:
            data.bar_number = bar_match.group(1)
        
        licensing_match = re.search(r'(?:Licensing\s*Authority)[^A-Za-z]*([A-Za-z][A-Za-z\s]+?)(?:,|\.)', text, re.IGNORECASE)
        if licensing_match:
            data.licensing_authority = licensing_match.group(1).strip().title()
        
        firm_match = re.search(r'(?:Law\s*Firm|Organization)[^A-Za-z]*([A-Za-z][^,\n]{5,60})', text, re.IGNORECASE)
        if firm_match:
            data.law_firm_name = re.sub(r'\s+', ' ', firm_match.group(1).strip())
        
        if not data.country and data.state:
            data.country = "United States"
        
        return data
    
    def _calculate_confidence(self, data: AttorneyData) -> float:
        """confidence score. check if extraction is successful (>0.3)"""
        required = ['last_name', 'first_name']
        important = ['street_address', 'city', 'state', 'email']
        
        req_score = sum(1 for f in required if getattr(data, f)) / len(required) * 0.5
        imp_score = sum(1 for f in important if getattr(data, f)) / len(important) * 0.5
        
        return min(1.0, req_score + imp_score)
