"""Playwright browser controller for executing Computer Use actions (Async version)."""
import os
import time
import asyncio
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Playwright, Download

from config import SCREEN_WIDTH, SCREEN_HEIGHT, HEADLESS


# Fixed download directory - always use user's Downloads folder
DOWNLOADS_DIR = Path(os.path.expanduser("~/Downloads"))


def denormalize_x(x: int, screen_width: int = SCREEN_WIDTH) -> int:
    """Convert normalized x coordinate (0-1000) to actual pixel coordinate."""
    return int(x / 1000 * screen_width)


def denormalize_y(y: int, screen_height: int = SCREEN_HEIGHT) -> int:
    """Convert normalized y coordinate (0-1000) to actual pixel coordinate."""
    return int(y / 1000 * screen_height)


class BrowserController:
    """
    Manages a Playwright browser instance for Computer Use actions (Async).
    
    DOWNLOAD HANDLING:
    - Downloads are saved to user's ~/Downloads folder
    - Downloads are tracked and can be retrieved after completion
    """

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._started = False
        self._pending_downloads: List[Download] = []
        self._completed_downloads: List[str] = []

    @property
    def is_started(self) -> bool:
        """Check if browser is started and page is available."""
        return self._started and self._page is not None
    
    @property
    def downloads_dir(self) -> Path:
        """Get the downloads directory."""
        return DOWNLOADS_DIR

    async def start(self, start_url: str = "about:blank", storage_state: Optional[Dict] = None) -> None:
        """Initialize and launch the browser with download support and optional auth state."""
        if self._started:
            # Browser already running, just navigate if needed
            if start_url and start_url != "about:blank" and self._page:
                try:
                    await self._page.goto(start_url)
                except Exception:
                    pass
            return
        
        # Ensure downloads directory exists
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[BROWSER] Downloads directory: {DOWNLOADS_DIR}")
            
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=HEADLESS)
        
        # Create context WITH download support and optional auth state
        context_args = {
            "viewport": {"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
            "accept_downloads": True,
        }
        
        if storage_state:
            print("[BROWSER] Injecting auth state (cookies/origins)")
            context_args["storage_state"] = storage_state
            
        self._context = await self._browser.new_context(**context_args)
        
        # Set up download handler
        self._context.on("download", self._on_download)
        
        self._page = await self._context.new_page()
        self._started = True
        if start_url:
            await self._page.goto(start_url)
    
    async def _on_download(self, download: Download) -> None:
        """Handle download events."""
        print(f"\n[DOWNLOAD] Download started: {download.suggested_filename}")
        self._pending_downloads.append(download)
        
        try:
            # Save to downloads directory
            save_path = DOWNLOADS_DIR / download.suggested_filename
            await download.save_as(str(save_path))
            self._completed_downloads.append(str(save_path))
            print(f"[DOWNLOAD] Saved to: {save_path}")
        except Exception as e:
            print(f"[DOWNLOAD] Error saving download: {e}")
    
    def get_latest_download(self) -> Optional[str]:
        """Get the path of the most recent download."""
        if self._completed_downloads:
            return self._completed_downloads[-1]
        return None

    async def stop(self) -> None:
        """Close browser and cleanup resources."""
        try:
            if self._browser:
                await self._browser.close()
        except Exception as e:
            print(f"[BROWSER] Warning closing browser: {e}")
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            print(f"[BROWSER] Warning stopping playwright: {e}")
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._started = False
        self._pending_downloads = []
        self._completed_downloads = []

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    async def get_screenshot_base64(self) -> str:
        """Capture current page screenshot as base64 string."""
        screenshot_bytes = await self.page.screenshot(type="png")
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def get_screenshot_bytes(self) -> bytes:
        """Capture current page screenshot as bytes."""
        return await self.page.screenshot(type="png")

    async def get_current_url(self) -> str:
        """Get the current page URL."""
        return self.page.url
    
    async def get_cookies(self) -> list:
        """
        Get all cookies from the browser context.
        
        Returns:
            List of cookie dictionaries with name, value, domain, etc.
        """
        if not self._context:
            return []
        return await self._context.cookies()
    
    async def get_cookies_for_domain(self, domain: str) -> str:
        """
        Get cookies formatted as a header string for a specific domain.
        
        Args:
            domain: Domain to filter cookies for (e.g., "projectgraphite.com")
            
        Returns:
            Cookie header string like "name1=value1; name2=value2"
        """
        all_cookies = await self.get_cookies()
        
        # Filter cookies for the specified domain
        matching_cookies = [
            c for c in all_cookies 
            if domain in c.get("domain", "")
        ]
        
        # Format as header string
        cookie_parts = [f"{c['name']}={c['value']}" for c in matching_cookies]
        return "; ".join(cookie_parts)
    
    async def get_auth_cookies_header(self) -> str:
        """
        Get authentication cookies for Graphite API calls.
        
        This is specifically for making authenticated API calls to Graphite
        using the session established after browser login.
        
        Returns:
            Cookie header string for Graphite API
        """
        return await self.get_cookies_for_domain("projectgraphite.com")

    async def execute_action(self, action_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a Computer Use action on the browser.
        
        Returns a dict with result info (url, error if any).
        """
        result: Dict[str, Any] = {}

        try:
            if action_name == "open_web_browser":
                # Browser is already open
                pass

            elif action_name == "navigate":
                url = args.get("url", "")
                await self.page.goto(url)

            elif action_name == "click_at":
                actual_x = denormalize_x(args["x"])
                actual_y = denormalize_y(args["y"])
                await self.page.mouse.click(actual_x, actual_y)

            elif action_name == "type_text_at":
                actual_x = denormalize_x(args["x"])
                actual_y = denormalize_y(args["y"])
                text = args.get("text", "")
                press_enter = args.get("press_enter", True)
                clear_before = args.get("clear_before_typing", True)

                await self.page.mouse.click(actual_x, actual_y)
                if clear_before:
                    await self.page.keyboard.press("Control+A")
                    await self.page.keyboard.press("Backspace")
                await self.page.keyboard.type(text)
                if press_enter:
                    await self.page.keyboard.press("Enter")

            elif action_name == "hover_at":
                actual_x = denormalize_x(args["x"])
                actual_y = denormalize_y(args["y"])
                await self.page.mouse.move(actual_x, actual_y)

            elif action_name == "scroll_document":
                direction = args.get("direction", "down")
                scroll_amount = 500
                if direction == "down":
                    await self.page.mouse.wheel(0, scroll_amount)
                elif direction == "up":
                    await self.page.mouse.wheel(0, -scroll_amount)
                elif direction == "right":
                    await self.page.mouse.wheel(scroll_amount, 0)
                elif direction == "left":
                    await self.page.mouse.wheel(-scroll_amount, 0)

            elif action_name == "scroll_at":
                actual_x = denormalize_x(args["x"])
                actual_y = denormalize_y(args["y"])
                direction = args.get("direction", "down")
                magnitude = args.get("magnitude", 800)
                # Move to position first
                await self.page.mouse.move(actual_x, actual_y)
                scroll_px = int(magnitude / 1000 * SCREEN_HEIGHT)
                if direction == "down":
                    await self.page.mouse.wheel(0, scroll_px)
                elif direction == "up":
                    await self.page.mouse.wheel(0, -scroll_px)
                elif direction == "right":
                    await self.page.mouse.wheel(scroll_px, 0)
                elif direction == "left":
                    await self.page.mouse.wheel(-scroll_px, 0)

            elif action_name == "key_combination":
                keys = args.get("keys", "")
                await self.page.keyboard.press(keys)

            elif action_name == "go_back":
                await self.page.go_back()

            elif action_name == "go_forward":
                await self.page.go_forward()

            elif action_name == "search":
                # Navigate to default search engine - using DuckDuckGo (doesn't block bots)
                print("🔍 DEBUG: Search action called - navigating to DuckDuckGo")
                await self.page.goto("https://duckduckgo.com")

            elif action_name == "wait_5_seconds":
                await asyncio.sleep(5)

            elif action_name == "drag_and_drop":
                start_x = denormalize_x(args["x"])
                start_y = denormalize_y(args["y"])
                end_x = denormalize_x(args["destination_x"])
                end_y = denormalize_y(args["destination_y"])
                await self.page.mouse.move(start_x, start_y)
                await self.page.mouse.down()
                await self.page.mouse.move(end_x, end_y)
                await self.page.mouse.up()

            else:
                result["warning"] = f"Unimplemented action: {action_name}"

            # Wait for page to stabilize - IMPROVED to avoid blank screenshots
            try:
                # First wait for DOM content to be loaded
                await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                
                # Then try to wait for network to be idle (more reliable for SPAs)
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=2000)
                except:
                    pass  # Network might not go idle on some pages, that's OK
                
                # Smart wait: Check if page has visible content, retry if blank
                for _ in range(5):  # Max 5 retries, 300ms each = 1.5s max extra
                    try:
                        # Check if body has any visible content
                        body_content = await self.page.evaluate("""
                            () => {
                                const body = document.body;
                                if (!body) return '';
                                // Check if there's meaningful content (not just loading spinners)
                                const text = body.innerText || '';
                                const hasImages = body.querySelectorAll('img').length > 0;
                                const hasButtons = body.querySelectorAll('button, a, input').length > 0;
                                // Return indicator of content presence
                                return (text.trim().length > 50 || hasImages || hasButtons) ? 'content' : 'empty';
                            }
                        """)
                        if body_content == 'content':
                            break  # Page has content, we're good
                    except:
                        pass
                    await asyncio.sleep(0.3)  # Wait a bit and retry
                    
            except Exception as e:
                print(f"[BROWSER] Load state wait warning: {e}")
                pass
            
            # Small final delay for any remaining animations/transitions
            await asyncio.sleep(0.3)

        except Exception as e:
            result["error"] = str(e)

        result["url"] = await self.get_current_url()
        return result
