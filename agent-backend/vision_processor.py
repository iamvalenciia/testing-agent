"""
Vision Processor - Process ticket images using Gemini Vision AI.

Provides:
- OCR text extraction from ticket screenshots
- Image description for agent context
- Maximum 3 images per message to control token costs

Usage:
    processor = get_vision_processor()
    texts = await processor.extract_text_from_images(images)
    descriptions = await processor.describe_images(images)
"""
import os
import base64
from typing import List, Optional
from dataclasses import dataclass

from google import genai
from google.genai import types


@dataclass
class ImageProcessingResult:
    """Result from processing an image."""
    extracted_text: Optional[str] = None
    description: Optional[str] = None
    error: Optional[str] = None


class VisionProcessor:
    """Process images using Gemini Vision AI."""
    
    # Maximum images per message to control token costs
    MAX_IMAGES = 3
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Vision Processor.
        
        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash"
    
    async def extract_text_from_images(
        self, 
        images: List[bytes],
        max_images: int = None
    ) -> List[ImageProcessingResult]:
        """Extract text from ticket screenshots using OCR.
        
        Args:
            images: List of image bytes
            max_images: Override max images limit
            
        Returns:
            List of ImageProcessingResult with extracted text
        """
        limit = max_images or self.MAX_IMAGES
        images_to_process = images[:limit]
        results = []
        
        for i, image_bytes in enumerate(images_to_process):
            try:
                image_b64 = base64.b64encode(image_bytes).decode()
                
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part(text="""Extract ALL visible text from this ticket screenshot. 
Include:
- Ticket ID, title, description
- Field names and values
- Labels, tags, status
- Any error messages or validation text

Format as structured text. Be thorough - don't miss any text."""),
                                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                            ]
                        )
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=2000,
                    )
                )
                
                if response and response.candidates:
                    results.append(ImageProcessingResult(
                        extracted_text=response.text.strip()
                    ))
                else:
                    results.append(ImageProcessingResult(
                        error="No response from Vision AI"
                    ))
                    
            except Exception as e:
                print(f"[VISION] Error extracting text from image {i+1}: {e}")
                results.append(ImageProcessingResult(
                    error=str(e)
                ))
        
        return results
    
    async def describe_images(
        self, 
        images: List[bytes],
        context: str = ""
    ) -> List[ImageProcessingResult]:
        """Generate descriptions of ticket images for agent context.
        
        Args:
            images: List of image bytes
            context: Optional context about what to look for
            
        Returns:
            List of ImageProcessingResult with descriptions
        """
        images_to_process = images[:self.MAX_IMAGES]
        results = []
        
        base_prompt = """Describe this ticket/bug report screenshot concisely. Focus on:
1. What page/screen is shown
2. Key information visible (ticket ID, status, fields)
3. Any errors, warnings, or important UI elements
4. The current state of the form/interface

Keep description to 2-3 sentences max."""
        
        if context:
            base_prompt += f"\n\nAdditional context: {context}"
        
        for i, image_bytes in enumerate(images_to_process):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part(text=base_prompt),
                                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                            ]
                        )
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=300,
                    )
                )
                
                if response and response.candidates:
                    results.append(ImageProcessingResult(
                        description=response.text.strip()
                    ))
                else:
                    results.append(ImageProcessingResult(
                        error="No response from Vision AI"
                    ))
                    
            except Exception as e:
                print(f"[VISION] Error describing image {i+1}: {e}")
                results.append(ImageProcessingResult(
                    error=str(e)
                ))
        
        return results
    
    async def process_ticket_images(
        self, 
        images: List[bytes],
        extract_text: bool = True,
        describe: bool = False
    ) -> str:
        """Process ticket images and return combined context for agent.
        
        This is the main method to call when processing user-uploaded images.
        
        Args:
            images: List of image bytes
            extract_text: Whether to extract text via OCR
            describe: Whether to generate descriptions
            
        Returns:
            Combined context string for the agent
        """
        if not images:
            return ""
        
        if len(images) > self.MAX_IMAGES:
            print(f"[VISION] Warning: {len(images)} images provided, limiting to {self.MAX_IMAGES}")
        
        context_parts = []
        
        if extract_text:
            text_results = await self.extract_text_from_images(images)
            for i, result in enumerate(text_results):
                if result.extracted_text:
                    context_parts.append(f"[Image {i+1} - Extracted Text]\n{result.extracted_text}")
                elif result.error:
                    context_parts.append(f"[Image {i+1} - Error: {result.error}]")
        
        if describe:
            desc_results = await self.describe_images(images)
            for i, result in enumerate(desc_results):
                if result.description:
                    context_parts.append(f"[Image {i+1} - Description]\n{result.description}")
        
        return "\n\n".join(context_parts)


# Singleton instance
_vision_processor: Optional[VisionProcessor] = None


def get_vision_processor() -> VisionProcessor:
    """Get the singleton VisionProcessor instance."""
    global _vision_processor
    if _vision_processor is None:
        _vision_processor = VisionProcessor()
    return _vision_processor
