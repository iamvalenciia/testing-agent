"""Visual Navigator - Gemini-powered visual element detection and navigation.

This module provides visual grounding capabilities using Gemini 2.5's
multimodal vision API to detect UI elements by description and return
coordinates for click actions.

Key features:
- Find elements by visual description (no CSS selectors needed)
- Extract text from screen regions (OCR)
- Wait for visual cues to appear
- Confidence scoring for element detection
"""

import base64
import re
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass

from google import genai
from google.genai import types

from config import GOOGLE_API_KEY


@dataclass
class ElementLocation:
    """Result of visual element detection."""
    x: int
    y: int
    width: Optional[int] = None
    height: Optional[int] = None
    confidence: float = 0.0
    description: str = ""


class VisualNavigator:
    """
    Visual element detection and navigation using Gemini multimodal.
    
    Uses Gemini 2.5 Flash to analyze screenshots and locate UI elements
    based on natural language descriptions. This replaces brittle CSS
    selectors with robust visual grounding.
    
    Example:
        navigator = VisualNavigator(browser)
        await navigator.click_element_by_description("the blue 'Submit' button")
    """
    
    MODEL_NAME = "gemini-2.5-flash-preview-05-20"
    
    def __init__(self, browser_controller):
        """
        Initialize the visual navigator.
        
        Args:
            browser_controller: BrowserController instance for screenshots and actions
        """
        self.browser = browser_controller
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self._last_screenshot: Optional[bytes] = None
    
    async def _get_screenshot_bytes(self) -> bytes:
        """Get current screenshot and cache it."""
        self._last_screenshot = await self.browser.get_screenshot_bytes()
        return self._last_screenshot
    
    async def find_element_coordinates(
        self, 
        description: str,
        screenshot: Optional[bytes] = None
    ) -> Optional[ElementLocation]:
        """
        Find UI element coordinates using Gemini vision.
        
        Args:
            description: Natural language description of the element
                        (e.g., "the 'Login' button", "email input field")
            screenshot: Optional pre-captured screenshot, captures new if None
        
        Returns:
            ElementLocation with x, y coordinates and confidence, or None if not found
        """
        if screenshot is None:
            screenshot = await self._get_screenshot_bytes()
        
        # Prepare the prompt for Gemini
        prompt = f"""Analyze this screenshot and find the UI element matching this description:
"{description}"

IMPORTANT: Return ONLY a JSON object with these fields:
- found: boolean (true if element was found)
- x: integer (center x coordinate in pixels)
- y: integer (center y coordinate in pixels)  
- width: integer (approximate width in pixels)
- height: integer (approximate height in pixels)
- confidence: float (0.0 to 1.0, how confident you are)
- element_text: string (the actual text on the element if any)

If the element is NOT found, return: {{"found": false}}

Example response for a found element:
{{"found": true, "x": 450, "y": 320, "width": 120, "height": 40, "confidence": 0.95, "element_text": "Submit"}}

Respond ONLY with valid JSON, no other text."""

        try:
            # Create multimodal content with image
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=[
                    types.Content(parts=[
                        types.Part.from_bytes(data=screenshot, mime_type="image/png"),
                        types.Part(text=prompt)
                    ])
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temp for precise detection
                )
            )
            
            if not response.candidates:
                print("⚠️ VisualNavigator: No response from Gemini")
                return None
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{[^{}]+\}', response_text, re.DOTALL)
            if not json_match:
                print(f"⚠️ VisualNavigator: Could not parse JSON from: {response_text[:200]}")
                return None
            
            import json
            result = json.loads(json_match.group())
            
            if not result.get("found", False):
                print(f"🔍 VisualNavigator: Element not found: '{description}'")
                return None
            
            location = ElementLocation(
                x=result.get("x", 0),
                y=result.get("y", 0),
                width=result.get("width"),
                height=result.get("height"),
                confidence=result.get("confidence", 0.5),
                description=result.get("element_text", description)
            )
            
            print(f"✅ VisualNavigator: Found '{description}' at ({location.x}, {location.y}) conf={location.confidence:.2f}")
            return location
            
        except Exception as e:
            print(f"❌ VisualNavigator error: {e}")
            return None
    
    async def click_element_by_description(self, description: str) -> bool:
        """
        Find element visually and click on it.
        
        Args:
            description: Natural language description of element to click
        
        Returns:
            True if element was found and clicked, False otherwise
        """
        location = await self.find_element_coordinates(description)
        
        if location is None:
            return False
        
        if location.confidence < 0.3:
            print(f"⚠️ VisualNavigator: Low confidence ({location.confidence:.2f}), skipping click")
            return False
        
        # Execute the click at the coordinates
        await self.browser.page.mouse.click(location.x, location.y)
        print(f"🖱️ VisualNavigator: Clicked at ({location.x}, {location.y})")
        return True
    
    async def type_in_element_by_description(
        self, 
        description: str, 
        text: str,
        clear_first: bool = True
    ) -> bool:
        """
        Find input element visually and type text into it.
        
        Args:
            description: Description of the input field
            text: Text to type
            clear_first: Clear existing content before typing
        
        Returns:
            True if successful, False otherwise
        """
        location = await self.find_element_coordinates(description)
        
        if location is None:
            return False
        
        # Click to focus the element
        await self.browser.page.mouse.click(location.x, location.y)
        
        if clear_first:
            await self.browser.page.keyboard.press("Control+A")
            await self.browser.page.keyboard.press("Backspace")
        
        await self.browser.page.keyboard.type(text)
        print(f"⌨️ VisualNavigator: Typed in '{description}'")
        return True
    
    async def wait_for_visual_cue(
        self, 
        description: str, 
        timeout_seconds: int = 10,
        poll_interval: float = 1.0
    ) -> bool:
        """
        Wait until a visual element appears on screen.
        
        Args:
            description: Description of element to wait for
            timeout_seconds: Maximum time to wait
            poll_interval: Seconds between checks
        
        Returns:
            True if element appeared, False if timeout
        """
        import asyncio
        
        elapsed = 0.0
        while elapsed < timeout_seconds:
            location = await self.find_element_coordinates(description)
            
            if location is not None and location.confidence >= 0.5:
                print(f"✅ VisualNavigator: Visual cue appeared: '{description}'")
                return True
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        print(f"⏰ VisualNavigator: Timeout waiting for: '{description}'")
        return False
    
    async def extract_text_from_screen(
        self, 
        region: Optional[Tuple[int, int, int, int]] = None
    ) -> str:
        """
        Extract visible text from screen (OCR).
        
        Args:
            region: Optional (x1, y1, x2, y2) bounding box, or full screen if None
        
        Returns:
            Extracted text as string
        """
        screenshot = await self._get_screenshot_bytes()
        
        region_desc = "the entire screen"
        if region:
            region_desc = f"the region from ({region[0]}, {region[1]}) to ({region[2]}, {region[3]})"
        
        prompt = f"""Extract and return ALL visible text from {region_desc}.
Return the text exactly as it appears, preserving formatting where possible.
If there are buttons, links, or labels, include them.
Respond with ONLY the extracted text, nothing else."""

        try:
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=[
                    types.Content(parts=[
                        types.Part.from_bytes(data=screenshot, mime_type="image/png"),
                        types.Part(text=prompt)
                    ])
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                )
            )
            
            if response.candidates:
                return response.text.strip()
            return ""
            
        except Exception as e:
            print(f"❌ VisualNavigator OCR error: {e}")
            return ""
    
    async def list_all_clickable_elements(self) -> List[Dict[str, Any]]:
        """
        Detect all clickable elements on the current screen.
        
        Returns:
            List of detected elements with coordinates and descriptions
        """
        screenshot = await self._get_screenshot_bytes()
        
        prompt = """Analyze this screenshot and list ALL clickable elements (buttons, links, inputs).

Return a JSON array where each element has:
- type: "button" | "link" | "input" | "checkbox" | "dropdown" | "other"
- text: the visible text/label
- x: center x coordinate
- y: center y coordinate
- description: brief description of what this element does

Example:
[
  {"type": "button", "text": "Submit", "x": 450, "y": 300, "description": "Form submit button"},
  {"type": "input", "text": "", "x": 300, "y": 200, "description": "Email input field"}
]

Return ONLY valid JSON array."""

        try:
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=[
                    types.Content(parts=[
                        types.Part.from_bytes(data=screenshot, mime_type="image/png"),
                        types.Part(text=prompt)
                    ])
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                )
            )
            
            if not response.candidates:
                return []
            
            response_text = response.text.strip()
            
            # Extract JSON array from response
            import json
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                return json.loads(json_match.group())
            return []
            
        except Exception as e:
            print(f"❌ VisualNavigator list elements error: {e}")
            return []


# Singleton instance factory
_navigator: Optional[VisualNavigator] = None


def get_visual_navigator(browser_controller) -> VisualNavigator:
    """Get or create a VisualNavigator instance."""
    global _navigator
    if _navigator is None or _navigator.browser != browser_controller:
        _navigator = VisualNavigator(browser_controller)
    return _navigator
