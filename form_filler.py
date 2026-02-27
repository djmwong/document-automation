"""
Browser automation for form filling using Playwright.
"""
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from models import ExtractedFormData, PassportData, AttorneyData

logger = logging.getLogger(__name__)

STATE_CODES = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'district of columbia': 'DC', 'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI',
    'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
    'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME',
    'maryland': 'MD', 'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN',
    'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE',
    'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM',
    'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
    'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI',
    'south carolina': 'SC', 'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX',
    'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
    'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY'
}


class FormFiller:
    """Playwright-based form filler for legal documentation forms."""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.screenshot_dir = Path(__file__).parent / "screenshots"
        self.screenshot_dir.mkdir(exist_ok=True)
    
    async def fill_form(
        self, 
        data: ExtractedFormData, 
        target_url: str = "https://mendrika-alma.github.io/form-submission/"
    ) -> Optional[str]:
        """Fill the target form with extracted data and return screenshot path."""
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(viewport={"width": 1280, "height": 1024})
            page = await context.new_page()
            
            try:
                await page.goto(target_url, wait_until="networkidle")
                await page.wait_for_timeout(1000)
                
                if data.attorney:
                    await self._fill_attorney_section(page, data.attorney)
                    await self._fill_eligibility_section(page, data.attorney)
                
                if data.passport:
                    await self._fill_passport_section(page, data.passport)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = self.screenshot_dir / f"form_filled_{timestamp}.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)
                
                if not self.headless:
                    await page.wait_for_timeout(60000)
                
                return str(screenshot_path)
                
            except Exception as e:
                logger.error(f"Form filling failed: {e}")
                raise
            finally:
                await browser.close()
    
    async def _fill_attorney_section(self, page, attorney: AttorneyData):
        """Fill Part 1: Attorney/Representative Information."""
        if attorney.online_account_number:
            await page.locator('#online-account').fill(attorney.online_account_number)
        if attorney.last_name:
            await page.locator('#family-name').fill(attorney.last_name)
        if attorney.first_name:
            await page.locator('#given-name').fill(attorney.first_name)
        if attorney.middle_name:
            await page.locator('#middle-name').fill(attorney.middle_name)
        if attorney.street_address:
            await page.locator('#street-number').fill(attorney.street_address)
        if attorney.apt_ste_flr:
            await page.locator('#apt-number').fill(attorney.apt_ste_flr)
        if attorney.city:
            await page.locator('#city').fill(attorney.city)
        if attorney.state:
            state_code = self._normalize_state_code(attorney.state)
            try:
                await page.locator('#state').select_option(value=state_code)
            except Exception:
                pass
        if attorney.zip_code:
            await page.locator('#zip').fill(attorney.zip_code)
        if attorney.country:
            await page.locator('#country').fill(attorney.country)
        if attorney.daytime_phone:
            await page.locator('#daytime-phone').fill(attorney.daytime_phone)
        if attorney.mobile_phone:
            await page.locator('#mobile-phone').fill(attorney.mobile_phone)
        if attorney.email:
            await page.locator('#email').fill(str(attorney.email))
    
    async def _fill_eligibility_section(self, page, attorney: AttorneyData):
        """Fill Part 2: Eligibility Information."""
        if attorney.licensing_authority:
            await page.locator('#licensing-authority').fill(attorney.licensing_authority)
        if attorney.bar_number:
            await page.locator('#bar-number').fill(attorney.bar_number)
        if attorney.law_firm_name:
            await page.locator('#law-firm').fill(attorney.law_firm_name)
    
    async def _fill_passport_section(self, page, passport: PassportData):
        """Fill Part 3: Passport Information for Beneficiary."""
        part3 = page.locator('text=Part 3. Passport Information').first
        if await part3.count() > 0:
            await part3.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)
        
        if passport.last_name:
            await page.locator('#passport-surname').fill(passport.last_name)
        
        # Handle duplicate ID bug in form (both first/middle name share same ID)
        given_name_inputs = page.locator('#passport-given-names')
        count = await given_name_inputs.count()
        if count >= 1 and passport.first_name:
            await given_name_inputs.nth(0).fill(passport.first_name)
        if count >= 2 and passport.middle_name:
            await given_name_inputs.nth(1).fill(passport.middle_name)
        
        if passport.passport_number:
            await page.locator('#passport-number').fill(passport.passport_number)
        if passport.country_of_issue:
            await page.locator('#passport-country').fill(passport.country_of_issue)
        if passport.nationality:
            await page.locator('#passport-nationality').fill(passport.nationality)
        if passport.date_of_birth:
            await page.locator('#passport-dob').fill(self._normalize_date(passport.date_of_birth))
        if passport.place_of_birth:
            await page.locator('#passport-pob').fill(passport.place_of_birth)
        if passport.sex:
            try:
                await page.locator('#passport-sex').select_option(value=passport.sex)
            except:
                pass
        if passport.date_of_issue:
            await page.locator('#passport-issue-date').fill(self._normalize_date(passport.date_of_issue))
        if passport.date_of_expiration:
            await page.locator('#passport-expiry-date').fill(self._normalize_date(passport.date_of_expiration))
    
    def _normalize_state_code(self, state: str) -> str:
        """Convert state name to 2-letter code."""
        if len(state) == 2:
            return state.upper()
        return STATE_CODES.get(state.lower(), state.upper()[:2])
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date to YYYY-MM-DD format."""
        if not date_str:
            return ""
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            return date_str
        try:
            import dateparser
            parsed = dateparser.parse(date_str)
            if parsed:
                return parsed.strftime("%Y-%m-%d")
        except:
            pass
        return date_str


async def fill_form_from_data(data: ExtractedFormData, headless: bool = False) -> Optional[str]:
    """Convenience function to fill form from extracted data."""
    filler = FormFiller(headless=headless)
    return await filler.fill_form(data)
