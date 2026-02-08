"""Browser session manager for Instagram login persistence"""

import asyncio
import json
from typing import Optional
from pathlib import Path

from .browser_utils import is_browser_closed_error, BrowserClosedError
from ...utils.logger import get_logger

logger = get_logger(__name__)

# Use domcontentloaded instead of networkidle - Instagram has continuous background
# requests and networkidle often times out or triggers ERR_HTTP_RESPONSE_CODE_FAILURE
INSTAGRAM_WAIT_UNTIL = "domcontentloaded"
INSTAGRAM_NAV_TIMEOUT = 60000

try:
    from playwright.async_api import Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None


class BrowserSessionManager:
    """
    Manages Instagram login sessions using browser cookies.
    
    Features:
    - Save/load cookies for session persistence
    - Automatic login detection
    - Session validation
    """
    
    def __init__(self, sessions_dir: str = "data/sessions"):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
    
    def get_session_file(self, account_id: str) -> Path:
        """Get session file path for an account"""
        return self.sessions_dir / f"{account_id}_cookies.json"
    
    async def save_session(self, account_id: str, page: Page):
        """
        Save current session cookies
        
        Args:
            account_id: Account identifier
            page: Playwright Page instance
        """
        if not PLAYWRIGHT_AVAILABLE:
            return
        
        try:
            cookies = await page.context.cookies()
            session_file = self.get_session_file(account_id)
            
            with open(session_file, "w") as f:
                json.dump(cookies, f, indent=2)
            
            logger.info(
                "Session saved",
                account_id=account_id,
                cookie_count=len(cookies),
            )
        except Exception as e:
            logger.error(
                "Failed to save session",
                account_id=account_id,
                error=str(e),
            )
    
    async def load_session(self, account_id: str, page: Page) -> bool:
        """
        Load saved session cookies
        
        Args:
            account_id: Account identifier
            page: Playwright Page instance
            
        Returns:
            True if session was loaded, False otherwise
        """
        if not PLAYWRIGHT_AVAILABLE:
            return False
        
        session_file = self.get_session_file(account_id)
        
        if not session_file.exists():
            logger.debug("No saved session found", account_id=account_id)
            return False
        
        try:
            with open(session_file, "r") as f:
                cookies = json.load(f)
            
            await page.context.add_cookies(cookies)
            
            logger.info(
                "Session loaded",
                account_id=account_id,
                cookie_count=len(cookies),
            )
            
            return True
        except Exception as e:
            logger.error(
                "Failed to load session",
                account_id=account_id,
                error=str(e),
            )
            return False
    
    async def _dismiss_cookie_consent(self, page: Page) -> None:
        """
        Dismiss Instagram cookie consent banner so it doesn't block the page.
        Scrolls the button into view and uses force click to handle off-screen/hidden popups.
        """
        if not PLAYWRIGHT_AVAILABLE:
            return
        # Reset zoom and ensure full viewport visible (handles "hidden inside" popup)
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
        except Exception:
            pass
        # Common cookie consent button texts (Instagram varies by region)
        cookie_selectors = [
            'button:has-text("Accept All")',
            'button:has-text("Allow essential and optional cookies")',
            'button:has-text("Allow all cookies")',
            'button:has-text("Only allow essential cookies")',
            'button:has-text("Accept")',
            'button:has-text("Allow")',
            '[role="button"]:has-text("Accept All")',
            '[role="button"]:has-text("Accept")',
            'div[role="dialog"] button:has-text("Accept")',
            'div[role="dialog"] button:has-text("Allow")',
        ]
        for sel in cookie_selectors:
            try:
                btn = page.locator(sel).first
                await btn.wait_for(state="attached", timeout=2000)
                # Ensure button is in view (fixes popup hidden off-screen)
                await btn.scroll_into_view_if_needed(timeout=2000)
                await asyncio.sleep(0.3)
                await btn.click(timeout=3000, force=True)
                logger.info("Cookie consent dismissed", selector=sel)
                await asyncio.sleep(1)
                return
            except Exception:
                continue

    async def _dismiss_post_login_prompts(self, page: Page) -> None:
        """
        Dismiss Instagram post-login dialogs: "Save your login info?", "Turn on Notifications", etc.
        These block the feed and prevent is_logged_in from detecting the DM icon.
        """
        if not PLAYWRIGHT_AVAILABLE:
            return
        prompts = [
            'button:has-text("Not Now")',
            'button:has-text("Not now")',
            'div[role="button"]:has-text("Not Now")',
            'a:has-text("Not Now")',
            'button:has-text("Save Info")',
        ]
        for _ in range(3):  # May have multiple dialogs (Save login -> Notifications)
            dismissed = False
            for sel in prompts:
                try:
                    btn = page.locator(sel).first
                    await btn.wait_for(state="visible", timeout=2000)
                    await btn.scroll_into_view_if_needed(timeout=1000)
                    await btn.click(timeout=3000, force=True)
                    logger.info("Dismissed post-login prompt", selector=sel)
                    await asyncio.sleep(1)
                    dismissed = True
                    break
                except Exception:
                    continue
            if not dismissed:
                break

    async def is_logged_in(self, page: Page) -> bool:
        """
        Check if user is logged into Instagram
        
        Args:
            page: Playwright Page instance
            
        Returns:
            True if logged in, False otherwise
        """
        if not PLAYWRIGHT_AVAILABLE:
            return False
        
        try:
            # Navigate to Instagram home (domcontentloaded avoids networkidle timeout on Instagram)
            await page.goto(
                "https://www.instagram.com/",
                wait_until=INSTAGRAM_WAIT_UNTIL,
                timeout=INSTAGRAM_NAV_TIMEOUT,
            )
            await asyncio.sleep(1)
            await self._dismiss_cookie_consent(page)
            await self._dismiss_post_login_prompts(page)

            # Check for login indicators - multiple selectors for different layouts
            logged_in_indicators = [
                'a[href*="/direct/"]',   # DM icon
                'a[href="/"]',           # Home icon
                'svg[aria-label="Home"]',
                'svg[aria-label="Messenger"]',
                'a[href*="/explore/"]',  # Explore tab
            ]
            for selector in logged_in_indicators:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        logger.debug("Logged in detected", indicator=selector)
                        return True
                except Exception:
                    continue
            
            # Check for login page indicators
            login_indicators = [
                'input[name="username"]',
                'button[type="submit"]',
            ]
            
            for selector in login_indicators:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        logger.debug("Not logged in - login page detected")
                        return False
                except Exception:
                    continue
            
            # Default to not logged in if we can't determine
            return False
            
        except Exception as e:
            if is_browser_closed_error(e):
                logger.debug("Browser closed during login check (likely shutdown)", error=str(e))
            else:
                logger.error("Error checking login status", error=str(e))
            return False
    
    async def login(
        self,
        page: Page,
        username: str,
        password: str,
        account_id: Optional[str] = None,
    ) -> bool:
        """
        Login to Instagram
        
        Args:
            page: Playwright Page instance
            username: Instagram username
            password: Instagram password
            account_id: Account identifier (for saving session)
            
        Returns:
            True if login successful, False otherwise
        """
        if not PLAYWRIGHT_AVAILABLE:
            return False
        
        try:
            # Load Instagram home first; then reach login form by clicking "Log in" to avoid
            # direct request to /accounts/login/ which is often blocked on datacenter IPs
            home_url = "https://www.instagram.com/"
            login_url = "https://www.instagram.com/accounts/login/"
            last_err = None
            reached_login_form = False
            for attempt in range(3):
                try:
                    await page.goto(
                        home_url,
                        wait_until=INSTAGRAM_WAIT_UNTIL,
                        timeout=INSTAGRAM_NAV_TIMEOUT,
                    )
                    await asyncio.sleep(2)
                    await self._dismiss_cookie_consent(page)
                    # Prefer clicking "Log in" from home so navigation is same-origin (less likely blocked)
                    try:
                        login_link = await page.query_selector('a[href*="/accounts/login"]')
                        if login_link:
                            await login_link.click()
                            await page.wait_for_load_state(INSTAGRAM_WAIT_UNTIL, timeout=15000)
                            await asyncio.sleep(1)
                            reached_login_form = True
                            break
                    except Exception:
                        pass
                    # Fallback: direct navigation to login URL
                    await page.goto(
                        login_url,
                        wait_until=INSTAGRAM_WAIT_UNTIL,
                        timeout=INSTAGRAM_NAV_TIMEOUT,
                    )
                    await asyncio.sleep(2)
                    await self._dismiss_cookie_consent(page)
                    reached_login_form = True
                    break
                except Exception as e:
                    last_err = e
                    err_str = str(e)
                    if attempt < 2:
                        logger.warning(
                            "Login page nav failed, retrying",
                            attempt=attempt + 1,
                            error=err_str[:120],
                        )
                        await asyncio.sleep(5)
            if not reached_login_form and last_err is not None:
                if "ERR_HTTP_RESPONSE_CODE_FAILURE" in str(last_err) or "403" in str(last_err):
                    logger.error(
                        "Instagram is blocking browser access (login page returned an error). "
                        "Common causes: server/datacenter IP, or automation detection. "
                        "Try: 1) Use a residential proxy in account settings, 2) Run from a home network, 3) Try again later.",
                        username=username,
                    )
                raise last_err

            # Wait for login form - try multiple selectors (Instagram may change layout)
            await asyncio.sleep(2)
            login_form_timeout = 15000
            username_selectors = [
                'input[name="username"]',
                'input[autocomplete="username"]',
                'input[aria-label*="phone" i], input[aria-label*="username" i], input[aria-label*="Phone" i]',
                'input[type="text"]',
            ]
            username_input = None
            for sel in username_selectors:
                try:
                    username_input = await page.wait_for_selector(sel, timeout=min(5000, login_form_timeout // len(username_selectors)))
                    if username_input:
                        break
                except Exception:
                    continue
            if not username_input:
                raise TimeoutError(
                    "Login form not found. Instagram may have changed the page or is showing a challenge. "
                    "Try a residential proxy or run from a home network."
                )
            await asyncio.sleep(0.5)

            # Fill in credentials - clear first to avoid leftover text
            await username_input.click(force=True)
            await username_input.fill("", timeout=2000)
            await asyncio.sleep(0.2)
            await username_input.fill(username, timeout=5000)
            pass_locator = page.locator('input[name="password"], input[type="password"]').first
            await pass_locator.fill(password, timeout=5000)
            await asyncio.sleep(0.3)
            
            # Click login button - Instagram may use different selectors
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Log in")',
                'button:has-text("Log In")',
                'div[role="button"]:has-text("Log in")',
                'form button',
            ]
            clicked = False
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    await btn.wait_for(state="visible", timeout=3000)
                    await btn.click(timeout=5000)
                    clicked = True
                    break
                except Exception:
                    continue
            if not clicked:
                raise TimeoutError("Could not find or click login button. Instagram may have changed the page.")
            
            # Wait for navigation (either to home or error)
            await page.wait_for_load_state(INSTAGRAM_WAIT_UNTIL, timeout=20000)
            await asyncio.sleep(2)
            # Dismiss "Save your login info?" / "Turn on Notifications" before checking
            await self._dismiss_post_login_prompts(page)

            # Check for login error messages (wrong password, etc.)
            try:
                err = page.locator('text=Sorry, your password was incorrect').first
                await err.wait_for(state="visible", timeout=2000)
                logger.warning("Login failed: incorrect password", username=username)
                return False
            except Exception:
                pass

            # Check if login was successful
            if await self.is_logged_in(page):
                logger.info("Login successful", username=username)
                
                # Save session if account_id provided
                if account_id:
                    await self.save_session(account_id, page)
                
                return True
            else:
                logger.warning("Login failed or still on login page", username=username)
                return False
                
        except Exception as e:
            if is_browser_closed_error(e):
                logger.debug("Browser closed during login (likely shutdown)", username=username)
                raise BrowserClosedError(str(e)) from e
            else:
                logger.error("Login error", username=username, error=str(e))
            return False
