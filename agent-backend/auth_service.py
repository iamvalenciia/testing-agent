"""
Auth Service - Graphite Authentication.

Handles automated login to Project Graphite to retrieve JWT tokens.
These credentials are shared between:
1. The Agent's Browser (so it starts logged in)
2. The Hammer Downloader (so it can hit protected APIs)
"""
import os
import asyncio
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, BrowserContext

from config import TEST_EMAIL, TEST_PASSWORD, TEST_WEBSITE


class AuthService:
    _instance = None
    _cookies: List[Dict] = []
    _storage_state: Dict = {}
    _jwt_token: Optional[str] = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = AuthService()
        return cls._instance
        
    def __init__(self):
        self.email = TEST_EMAIL
        self.password = TEST_PASSWORD
        self.website = TEST_WEBSITE
        
    async def login_and_capture_state(self) -> Dict[str, Any]:
        """
        Launches a headless browser, logs into Graphite, and captures JWT.
        Returns: Playwright storage_state dict (cookies + origins)
        """
        if not self.email or not self.password:
            print("⚠️ Missing credentials (TEST_EMAIL/TEST_PASSWORD). Skipping auth.")
            return {}
            
        print(f"[AUTH] Starting Graphite login to {self.website}...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # 1. Navigate to Graphite signin page
                login_url = f"{self.website}/signin"
                print(f"[AUTH] Navigating to {login_url}")
                await page.goto(login_url)
                await page.wait_for_load_state("networkidle")
                
                # 2. Wait for and fill email field
                # Graphite uses a standard input that might have Material UI or custom styling
                email_selectors = [
                    "input[type='email']",
                    "input[name='email']",
                    "input[placeholder*='email' i]",
                    "input[placeholder*='Email' i]",
                    "#email",
                    "[data-testid='email-input']",
                    "input.MuiInputBase-input",  # Material UI
                    "form input:first-of-type",
                ]
                
                email_filled = False
                for selector in email_selectors:
                    try:
                        if await page.is_visible(selector, timeout=2000):
                            await page.fill(selector, self.email)
                            print(f"[AUTH] Filled email using: {selector}")
                            email_filled = True
                            break
                    except:
                        continue
                
                if not email_filled:
                    # Last resort: find ANY visible input
                    inputs = await page.query_selector_all("input:visible")
                    if inputs:
                        await inputs[0].fill(self.email)
                        print("[AUTH] Filled email using first visible input")
                        email_filled = True
                    else:
                        print("[AUTH] ERROR: Could not find email input")
                        # Take screenshot for debugging
                        await page.screenshot(path="auth_debug_email.png")
                        return {}
                
                # 3. Fill password field
                password_selectors = [
                    "input[type='password']",
                    "input[name='password']",
                    "#password",
                    "[data-testid='password-input']",
                ]
                
                password_filled = False
                for selector in password_selectors:
                    try:
                        if await page.is_visible(selector, timeout=2000):
                            await page.fill(selector, self.password)
                            print(f"[AUTH] Filled password using: {selector}")
                            password_filled = True
                            break
                    except:
                        continue
                
                if not password_filled:
                    # Maybe need to click Next first?
                    next_buttons = ["button:has-text('Next')", "button:has-text('Continue')"]
                    for btn in next_buttons:
                        try:
                            if await page.is_visible(btn, timeout=1000):
                                await page.click(btn)
                                await page.wait_for_timeout(1500)
                                break
                        except:
                            continue
                    
                    # Try again for password
                    for selector in password_selectors:
                        try:
                            if await page.is_visible(selector, timeout=2000):
                                await page.fill(selector, self.password)
                                print(f"[AUTH] Filled password after Next: {selector}")
                                password_filled = True
                                break
                        except:
                            continue
                
                if not password_filled:
                    print("[AUTH] ERROR: Could not find password input")
                    await page.screenshot(path="auth_debug_password.png")
                    return {}
                
                # 4. Submit login
                submit_selectors = [
                    "button[type='submit']",
                    "button:has-text('Sign in')",
                    "button:has-text('Login')",
                    "button:has-text('Log in')",
                    "button.MuiButton-root",
                    "form button",
                ]
                
                submitted = False
                for selector in submit_selectors:
                    try:
                        if await page.is_visible(selector, timeout=1000):
                            await page.click(selector)
                            print(f"[AUTH] Clicked submit: {selector}")
                            submitted = True
                            break
                    except:
                        continue
                
                if not submitted:
                    # Try pressing Enter
                    await page.keyboard.press("Enter")
                    print("[AUTH] Pressed Enter to submit")
                
                # 5. Wait for login to complete
                print("[AUTH] Waiting for auth response...")
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)  # Extra wait for JWT to be set
                
                # 6. Capture storage state (cookies)
                storage_state = await context.storage_state()
                self._storage_state = storage_state
                self._cookies = storage_state.get("cookies", [])
                
                # 7. Extract JWT token
                for cookie in self._cookies:
                    if cookie["name"] == "jwt":
                        self._jwt_token = cookie["value"]
                        print(f"[AUTH] ✅ Captured JWT token ({len(self._jwt_token)} chars)")
                        break
                
                if not self._jwt_token:
                    # Check localStorage
                    jwt = await page.evaluate("localStorage.getItem('jwt') || localStorage.getItem('token')")
                    if jwt:
                        self._jwt_token = jwt
                        print(f"[AUTH] ✅ Captured JWT from localStorage")
                
                if self._jwt_token:
                    print(f"[AUTH] ✅ Login successful! JWT captured, {len(self._cookies)} cookies.")
                else:
                    print(f"[AUTH] ⚠️ Login completed but no JWT found. {len(self._cookies)} cookies captured.")
                    # Debug: print cookie names
                    print(f"[AUTH] Cookie names: {[c['name'] for c in self._cookies]}")
                
                return storage_state
                
            except Exception as e:
                print(f"❌ [AUTH] Login failed: {e}")
                import traceback
                traceback.print_exc()
                try:
                    await page.screenshot(path="auth_debug_error.png")
                except:
                    pass
                return {}
            finally:
                await browser.close()

    def get_cookies_dict(self) -> Dict[str, str]:
        """Get cookies as a dictionary for requests library."""
        return {c["name"]: c["value"] for c in self._cookies}
    
    def get_storage_state(self) -> Dict:
        """Get Playwright storage state."""
        return self._storage_state
    
    def get_jwt_token(self) -> Optional[str]:
        """Get the JWT token for Authorization header."""
        return self._jwt_token
    
    def get_auth_header(self) -> Dict[str, str]:
        """Get Authorization header for API calls."""
        if self._jwt_token:
            return {"Authorization": f"Bearer {self._jwt_token}"}
        return {}


def get_auth_service():
    return AuthService.get_instance()
