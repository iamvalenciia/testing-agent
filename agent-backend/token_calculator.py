"""
Token Calculator & Cost Estimator.

Provides utilities to:
1. Track token usage (using exact API metadata or estimation)
2. Calculate costs based on model pricing
3. Aggregate session usage
"""
from typing import Dict, Any, Optional
import tiktoken

# Pricing per 1M tokens (USD)
# Based on user provided data
PRICING = {
    "gemini-2.0-flash-lite": {
        "input": 0.075,
        "output": 0.30
    },
    "gemini-2.0-flash": {
        "input": 0.10,
        "output": 0.40
    },
    "gemini-2.5-flash-preview-09-2025": {
        "input": 0.30,
        "output": 2.50
    },
    "gemini-2.5-computer-use-preview-10-2025": {
        "input": 1.25,   # prompts <= 200k
        "output": 10.00
    },
    "gemini-embedding-001": {
        "input": 0.00,  # Free tier effectively for low usage, but paid is $0.15
        "output": 0.00
    }
}

class TokenCalculator:
    
    def __init__(self):
        # Use cl100k_base as a reasonable proxy for estimation if metadata missing
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens for a string using a standard tokenizer proxy."""
        if not text:
            return 0
        return len(self.tokenizer.encode(text))
    
    def calculate_cost(self, model_name: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for a given model and token usage."""
        
        # Normalize model name to match keys
        pricing_key = model_name
        if "computer-use" in model_name:
            pricing_key = "gemini-2.5-computer-use-preview-10-2025"
        elif "flash-lite" in model_name:
            pricing_key = "gemini-2.0-flash-lite"
        elif "flash" in model_name and "2.0" in model_name:
            pricing_key = "gemini-2.0-flash"
        
        if pricing_key not in PRICING:
            # Fallback or log warning
            return 0.0
            
        rates = PRICING[pricing_key]
        
        input_cost = (input_tokens / 1_000_000) * rates["input"]
        output_cost = (output_tokens / 1_000_000) * rates["output"]
        
        return input_cost + output_cost

# Singleton
_calculator = TokenCalculator()

def get_token_calculator() -> TokenCalculator:
    return _calculator
