"""
Passport data extraction using LLM vision first, then MRZ parsing (if LLM fails), and OCR fallback (if both fail).
"""
import re
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import logging

from models import PassportData

logger = logging.getLogger(__name__)

COUNTRY_CODES = {
    "USA": "United States", "GBR": "United Kingdom", "CAN": "Canada",
    "AUS": "Australia", "DEU": "Germany", "FRA": "France", "ITA": "Italy",
    "ESP": "Spain", "JPN": "Japan", "CHN": "China", "IND": "India",
    "BRA": "Brazil", "MEX": "Mexico", "KOR": "South Korea", "RUS": "Russia",
    "NLD": "Netherlands", "BEL": "Belgium", "CHE": "Switzerland",
    "AUT": "Austria", "SWE": "Sweden", "NOR": "Norway", "DNK": "Denmark",
    "FIN": "Finland", "POL": "Poland", "PRT": "Portugal", "GRC": "Greece",
    "IRL": "Ireland", "NZL": "New Zealand", "SGP": "Singapore",
    "HKG": "Hong Kong", "TWN": "Taiwan", "THA": "Thailand", "VNM": "Vietnam",
    "PHL": "Philippines", "IDN": "Indonesia", "MYS": "Malaysia",
    "ARG": "Argentina", "CHL": "Chile", "COL": "Colombia", "PER": "Peru",
    "ZAF": "South Africa", "EGY": "Egypt", "NGA": "Nigeria", "KEN": "Kenya",
    "ISR": "Israel", "ARE": "United Arab Emirates", "SAU": "Saudi Arabia",
    "TUR": "Turkey", "PAK": "Pakistan", "BGD": "Bangladesh",
}


class PassportExtractor:
    """Multi-strategy passport data extractor."""
    
    def __init__(self):
        self._nlp = None
    
    @property
    def nlp(self):
        """Lazy load spaCy model."""
        if self._nlp is None:
            try:
                import spacy
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                self._nlp = False
        return self._nlp if self._nlp else None
    
    def extract(self, file_path: Path, file_bytes: Optional[bytes] = None, use_llm: bool = True) -> PassportData:
        """Extract passport data using available methods."""
        # using LLM extraction first
        if use_llm:
            try:
                from extractors.llm_passport_extractor import LLMPassportExtractor, is_llm_available
                if is_llm_available():
                    llm_extractor = LLMPassportExtractor()
                    result = llm_extractor.extract(file_path, file_bytes)
                    if result and (result.passport_number or result.last_name):
                        return result
            except Exception as e:
                logger.warning(f"LLM extraction failed: {e}")
        
        images = self._get_images(file_path, file_bytes)
        
        # use MRZ extraction if LLM fails
        mrz_data = self._extract_mrz(images)
        if mrz_data and mrz_data.passport_number:
            mrz_data.extraction_method = "MRZ"
            mrz_data.confidence_score = 0.95
            return mrz_data
        
        # use OCR and NLP if both llm and mrz fail
        ocr_data = self._extract_via_ocr(images)
        if ocr_data:
            ocr_data.extraction_method = "OCR+NLP"
            ocr_data.confidence_score = 0.7
            return ocr_data
        
        return PassportData(extraction_method="FAILED", confidence_score=0.0)
    
    def _get_images(self, file_path: Path, file_bytes: Optional[bytes] = None) -> list:
        """convert document to PIL Images."""
        from PIL import Image
        import io
        
        images = []
        suffix = file_path.suffix.lower()
        
        try:
            if suffix == ".pdf":
                from pdf2image import convert_from_path, convert_from_bytes
                images = convert_from_bytes(file_bytes, dpi=300) if file_bytes else convert_from_path(str(file_path), dpi=300)
            else:
                images = [Image.open(io.BytesIO(file_bytes)) if file_bytes else Image.open(file_path)]
        except Exception as e:
            logger.error(f"Failed to load images: {e}")
        
        return images
    
    def _extract_mrz(self, images: list) -> Optional[PassportData]:
        """Extract data from MRZ using mrz library."""
        try:
            from mrz.checker.td3 import TD3CodeChecker
        except ImportError:
            return None
        
        for img in images:
            text = self._ocr_image(img)
            if not text:
                continue
            
            mrz_lines = self._find_mrz_lines(text)
            if mrz_lines:
                try:
                    checker = TD3CodeChecker(mrz_lines[0] + "\n" + mrz_lines[1])
                    if checker.result:
                        return self._parse_mrz_fields(checker.fields())
                except:
                    pass
        
        return None
    
    def _find_mrz_lines(self, text: str) -> Optional[Tuple[str, str]]:
        """Find MRZ lines in OCR text."""
        lines = text.upper().split('\n')
        mrz_pattern = re.compile(r'^[A-Z0-9<]{40,50}$')
        
        candidates = []
        for line in lines:
            cleaned = line.replace(' ', '').replace('«', '<').replace('‹', '<')
            cleaned = re.sub(r'[^A-Z0-9<]', '', cleaned)
            
            if mrz_pattern.match(cleaned) and 42 <= len(cleaned) <= 46:
                if len(cleaned) < 44:
                    cleaned += '<' * (44 - len(cleaned))
                elif len(cleaned) > 44:
                    cleaned = cleaned[:44]
                candidates.append(cleaned)
        
        return (candidates[0], candidates[1]) if len(candidates) >= 2 else None
    
    def _parse_mrz_fields(self, fields: dict) -> PassportData:
        """parse MRZ fields into PassportData."""
        surname = fields.get('surname', '').replace('<', ' ').strip()
        given_names = fields.get('name', '').replace('<', ' ').strip()
        
        name_parts = given_names.split()
        first_name = name_parts[0] if name_parts else None
        middle_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else None
        
        return PassportData(
            last_name=surname.title() if surname else None,
            first_name=first_name.title() if first_name else None,
            middle_name=middle_name.title() if middle_name else None,
            passport_number=fields.get('document_number', '').replace('<', ''),
            country_of_issue=COUNTRY_CODES.get(fields.get('country', ''), fields.get('country', '')),
            nationality=COUNTRY_CODES.get(fields.get('nationality', ''), fields.get('nationality', '')),
            date_of_birth=self._parse_mrz_date(fields.get('birth_date', '')),
            sex=fields.get('sex', '').upper() or None,
            date_of_expiration=self._parse_mrz_date(fields.get('expiry_date', '')),
        )
    
    def _parse_mrz_date(self, date_str: str) -> Optional[str]:
        """parse MRZ date (YYMMDD) to ISO format."""
        if not date_str or len(date_str) < 6:
            return None
        try:
            yy, mm, dd = int(date_str[:2]), int(date_str[2:4]), int(date_str[4:6])
            current_year = datetime.now().year % 100
            year = 1900 + yy if yy > current_year + 10 else 2000 + yy
            return f"{year:04d}-{mm:02d}-{dd:02d}"
        except:
            return None
    
    def _ocr_image(self, image) -> Optional[str]:
        """Run OCR on image."""
        try:
            import pytesseract
            return pytesseract.image_to_string(
                image, config='--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
            )
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return None
    
    def _extract_via_ocr(self, images: list) -> Optional[PassportData]:
        """OCR extraction"""
        try:
            import pytesseract
        except ImportError:
            return None
        
        for img in images:
            try:
                text = pytesseract.image_to_string(img, config='--psm 3')
                if text and len(text) >= 50:
                    data = self._extract_from_text(text)
                    if data.passport_number or data.last_name:
                        return data
            except:
                pass
        return None
    
    def _extract_from_text(self, text: str) -> PassportData:
        """extract passport fields from text using NERs and regex."""
        data = PassportData()
        
        for pattern in [
            r'(?:passport\s*(?:no|number|#)?[:\s]*)([A-Z0-9]{6,12})',
            r'\b([A-Z]{1,2}\d{6,9})\b',
            r'\b(\d{9})\b',
        ]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data.passport_number = match.group(1).upper()
                break
        
        #NERs
        if self.nlp:
            doc = self.nlp(text[:2000])
            persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
            if persons:
                parts = persons[0].split()
                if len(parts) >= 2:
                    data.first_name = parts[0]
                    data.last_name = parts[-1]
                    if len(parts) > 2:
                        data.middle_name = ' '.join(parts[1:-1])
        
        for pattern in [
            r'(?:date\s+of\s+birth|dob|birth\s*date)[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(?:date\s+of\s+birth|dob|birth\s*date)[:\s]*(\d{1,2}\s+[A-Za-z]+\s+\d{2,4})',
        ]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data.date_of_birth = self._normalize_date(match.group(1))
                break
        
        sex_match = re.search(r'(?:sex|gender)[:\s]*(M|F|MALE|FEMALE|X)', text, re.IGNORECASE)
        if sex_match:
            sex = sex_match.group(1).upper()
            data.sex = 'M' if sex in ('M', 'MALE') else 'F' if sex in ('F', 'FEMALE') else 'X'
        
        return data
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date to ISO format."""
        try:
            import dateparser
            parsed = dateparser.parse(date_str)
            return parsed.strftime("%Y-%m-%d") if parsed else date_str
        except:
            return date_str
