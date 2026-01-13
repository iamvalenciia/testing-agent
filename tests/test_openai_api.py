"""Test OpenAI API Key with GPT-5 models.

This module tests the OPENAI_API_KEY environment variable by making
simple API calls to gpt-5-mini and gpt-5-nano models.

Models tested:
- gpt-5-mini-2025-08-07: Cost-optimized reasoning and chat
- gpt-5-nano-2025-08-07: High-throughput tasks, simple instruction-following
"""
import os
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI


def test_gpt5_mini():
    """Test gpt-5-mini-2025-08-07 model with a simple query."""
    print("\n" + "="*60)
    print("Testing: gpt-5-mini-2025-08-07")
    print("="*60)
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("[FAILED] OPENAI_API_KEY environment variable not found!")
        return False
    
    print(f"[OK] API Key found (starts with: {api_key[:8]}...)")
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Using Chat Completions API with minimal parameters
        response = client.chat.completions.create(
            model="gpt-5-mini-2025-08-07",
            messages=[
                {"role": "user", "content": "Hola! Responde con una sola palabra: Funcionamos?"}
            ]
        )
        
        reply = response.choices[0].message.content
        print(f"[SUCCESS] Model responded:")
        print(f"   Response: {reply}")
        print(f"   Model: {response.model}")
        if response.usage:
            print(f"   Usage: {response.usage.prompt_tokens} prompt + {response.usage.completion_tokens} completion tokens")
        return True
        
    except Exception as e:
        print(f"[FAILED] {type(e).__name__}: {str(e)}")
        return False


def test_gpt5_nano():
    """Test gpt-5-nano-2025-08-07 model with a simple query."""
    print("\n" + "="*60)
    print("Testing: gpt-5-nano-2025-08-07")
    print("="*60)
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("[FAILED] OPENAI_API_KEY environment variable not found!")
        return False
    
    print(f"[OK] API Key found (starts with: {api_key[:8]}...)")
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Using Chat Completions API with minimal parameters
        response = client.chat.completions.create(
            model="gpt-5-nano-2025-08-07",
            messages=[
                {"role": "user", "content": "Hola! Responde con una sola palabra: Funcionamos?"}
            ]
        )
        
        reply = response.choices[0].message.content
        print(f"[SUCCESS] Model responded:")
        print(f"   Response: {reply}")
        print(f"   Model: {response.model}")
        if response.usage:
            print(f"   Usage: {response.usage.prompt_tokens} prompt + {response.usage.completion_tokens} completion tokens")
        return True
        
    except Exception as e:
        print(f"[FAILED] {type(e).__name__}: {str(e)}")
        return False


def main():
    """Run all OpenAI API tests."""
    print("\n" + "#"*60)
    print("# OpenAI API Key Validation Tests")
    print("# Models: gpt-5-mini, gpt-5-nano (2025-08-07)")
    print("#"*60)
    
    results = {
        "gpt-5-mini-2025-08-07": test_gpt5_mini(),
        "gpt-5-nano-2025-08-07": test_gpt5_nano()
    }
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    all_passed = True
    for model, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {model}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("All tests PASSED! Your OpenAI API key is working correctly.")
    else:
        print("Some tests FAILED. Please check your API key and model access.")
    print("="*60 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
