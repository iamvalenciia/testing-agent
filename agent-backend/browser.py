"""Playwright browser controller for executing Computer Use actions (Async version)."""
import time
import asyncio
import base64
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Playwright

from config import SCREEN_WIDTH, SCREEN_HEIGHT, HEADLESS


def denormalize_x(x: int, screen_width: int = SCREEN_WIDTH) -> int:
    """Convert normalized x coordinate (0-1000) to actual pixel coordinate."""
    return int(x / 1000 * screen_width)


def denormalize_y(y: int, screen_height: int = SCREEN_HEIGHT) -> int:
    """Convert normalized y coordinate (0-1000) to actual pixel coordinate."""
    return int(y / 1000 * screen_height)


class BrowserController:
    """Manages a Playwright browser instance for Computer Use actions (Async)."""

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._started = False

    @property
    def is_started(self) -> bool:
        """Check if browser is started and page is available."""
        return self._started and self._page is not None

    async def start(self, start_url: str = "about:blank") -> None:
        """Initialize and launch the browser."""
        if self._started:
            # Browser already running, just navigate if needed
            if start_url and start_url != "about:blank" and self._page:
                try:
                    await self._page.goto(start_url)
                except Exception:
                    pass
            return
            
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=HEADLESS)
        self._context = await self._browser.new_context(
            viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}
        )
        self._page = await self._context.new_page()
        self._started = True
        if start_url:
            await self._page.goto(start_url)

    async def stop(self) -> None:
        """Close browser and cleanup resources."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._started = False

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

            # Wait for page to stabilize
            try:
                await self.page.wait_for_load_state(timeout=5000)
            except:
                pass
            await asyncio.sleep(0.5)

        except Exception as e:
            result["error"] = str(e)

        result["url"] = await self.get_current_url()
        return result
