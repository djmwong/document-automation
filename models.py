"""Pydantic data models for document extraction."""
from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr


class PassportData(BaseModel):
    """Extracted passport data."""
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    passport_number: Optional[str] = None
    country_of_issue: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    place_of_birth: Optional[str] = None
    sex: Optional[Literal["M", "F", "X"]] = None
    date_of_issue: Optional[str] = None
    date_of_expiration: Optional[str] = None
    extraction_method: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class AttorneyData(BaseModel):
    """Extracted G-28 attorney data."""
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    street_address: Optional[str] = None
    apt_ste_flr: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    daytime_phone: Optional[str] = None
    mobile_phone: Optional[str] = None
    email: Optional[EmailStr] = None
    licensing_authority: Optional[str] = None
    bar_number: Optional[str] = None
    law_firm_name: Optional[str] = None
    online_account_number: Optional[str] = None
    extraction_method: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class ExtractedFormData(BaseModel):
    """Combined extraction results."""
    passport: Optional[PassportData] = None
    attorney: Optional[AttorneyData] = None
    raw_text: Optional[dict] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


US_STATES = {
    "alabama": "AL", "al": "AL", "alaska": "AK", "ak": "AK",
    "arizona": "AZ", "az": "AZ", "arkansas": "AR", "ar": "AR",
    "california": "CA", "ca": "CA", "colorado": "CO", "co": "CO",
    "connecticut": "CT", "ct": "CT", "delaware": "DE", "de": "DE",
    "district of columbia": "DC", "dc": "DC", "florida": "FL", "fl": "FL",
    "georgia": "GA", "ga": "GA", "hawaii": "HI", "hi": "HI",
    "idaho": "ID", "id": "ID", "illinois": "IL", "il": "IL",
    "indiana": "IN", "in": "IN", "iowa": "IA", "ia": "IA",
    "kansas": "KS", "ks": "KS", "kentucky": "KY", "ky": "KY",
    "louisiana": "LA", "la": "LA", "maine": "ME", "me": "ME",
    "maryland": "MD", "md": "MD", "massachusetts": "MA", "ma": "MA",
    "michigan": "MI", "mi": "MI", "minnesota": "MN", "mn": "MN",
    "mississippi": "MS", "ms": "MS", "missouri": "MO", "mo": "MO",
    "montana": "MT", "mt": "MT", "nebraska": "NE", "ne": "NE",
    "nevada": "NV", "nv": "NV", "new hampshire": "NH", "nh": "NH",
    "new jersey": "NJ", "nj": "NJ", "new mexico": "NM", "nm": "NM",
    "new york": "NY", "ny": "NY", "north carolina": "NC", "nc": "NC",
    "north dakota": "ND", "nd": "ND", "ohio": "OH", "oh": "OH",
    "oklahoma": "OK", "ok": "OK", "oregon": "OR", "or": "OR",
    "pennsylvania": "PA", "pa": "PA", "rhode island": "RI", "ri": "RI",
    "south carolina": "SC", "sc": "SC", "south dakota": "SD", "sd": "SD",
    "tennessee": "TN", "tn": "TN", "texas": "TX", "tx": "TX",
    "utah": "UT", "ut": "UT", "vermont": "VT", "vt": "VT",
    "virginia": "VA", "va": "VA", "washington": "WA", "wa": "WA",
    "west virginia": "WV", "wv": "WV", "wisconsin": "WI", "wi": "WI",
    "wyoming": "WY", "wy": "WY",
}


def normalize_state(state_str: Optional[str]) -> Optional[str]:
    """Normalize state to 2-letter code."""
    if not state_str:
        return None
    return US_STATES.get(state_str.lower().strip(), state_str.upper()[:2])
