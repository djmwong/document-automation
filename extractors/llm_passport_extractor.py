"""
LLM-based passport extraction using OpenAI GPT-4
"""
import base64
import json
import logging
import os
from pathlib import Path
from typing import Optional
from io import BytesIO

from models import PassportData

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are an expert in passport data extraction. Analyze this passport image and extract all visible information.

Return JSON with these fields (use null if not found):
{
  "last_name": "Family name / Surname",
  "first_name": "First given name",
  "middle_name": "Middle name(s) if any",
  "passport_number": "Document number",
  "country_of_issue": "Full country name",
  "nationality": "Nationality of holder",
  "date_of_birth": "YYYY-MM-DD format",
  "place_of_birth": "City/Place of birth",
  "sex": "M or F",
  "date_of_issue": "YYYY-MM-DD format",
  "date_of_expiration": "YYYY-MM-DD format"
}

Here are the instructions:
1. Read BOTH the visual zone (printed text) AND the MRZ (bottom lines)
2. Prefer visual zone labels (Surname, Given names, etc.) for names
3. Convert all dates to YYYY-MM-DD format
4. Return ONLY valid JSON"""


class LLMPassportExtractor:
    """Extract passport data using OpenAI GPT-4o"""
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self._client = OpenAI(api_key=api_key)
            except ImportError:
                pass
        return self._client
    
    def extract(self, file_path: Path, file_bytes: Optional[bytes] = None) -> Optional[PassportData]:
        if not self.client:
            return None
        
        image_base64, media_type = self._prepare_image(file_path, file_bytes)
        if not image_base64:
            return None
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT},
                        {"type": "image_url", "image_url": {
                            "url": f"data:{media_type};base64,{image_base64}",
                            "detail": "high"
                        }}
                    ]
                }],
                max_tokens=1000,
                temperature=0
            )
            
            result = self._parse_response(response.choices[0].message.content)
            if result:
                result.extraction_method = "LLM_OPENAI"
                result.confidence_score = 0.95
            return result
            
        except Exception as e:
            logger.error(f"OpenAI extraction failed: {e}")
            return None
    
    def _prepare_image(self, file_path: Path, file_bytes: Optional[bytes] = None) -> tuple:
        from PIL import Image
        
        try:
            suffix = file_path.suffix.lower()
            
            if suffix == ".pdf":
                from pdf2image import convert_from_path, convert_from_bytes
                images = convert_from_bytes(file_bytes, dpi=200) if file_bytes else convert_from_path(str(file_path), dpi=200)
                img = images[0] if images else None
            else:
                img = Image.open(BytesIO(file_bytes)) if file_bytes else Image.open(file_path)
            
            if not img:
                return None, None
            
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            #resize if too large
            max_size = 2000
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)), Image.LANCZOS)
            
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=95)
            return base64.b64encode(buffer.getvalue()).decode(), "image/jpeg"
            
        except Exception as e:
            logger.error(f"Image preparation failed: {e}")
            return None, None
    
    def _parse_response(self, response_text: str) -> Optional[PassportData]:
        """parse LLM JSON response into PassportData."""
        try:
            json_str = response_text.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]
            
            data = json.loads(json_str)
            
            return PassportData(
                last_name=data.get("last_name"),
                first_name=data.get("first_name"),
                middle_name=data.get("middle_name"),
                passport_number=data.get("passport_number"),
                country_of_issue=data.get("country_of_issue"),
                nationality=data.get("nationality"),
                date_of_birth=data.get("date_of_birth"),
                place_of_birth=data.get("place_of_birth"),
                sex=data.get("sex"),
                date_of_issue=data.get("date_of_issue"),
                date_of_expiration=data.get("date_of_expiration"),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return None


def is_llm_available() -> bool:
    """Check if OpenAI API key is configured."""
    return bool(os.getenv("OPENAI_API_KEY"))
