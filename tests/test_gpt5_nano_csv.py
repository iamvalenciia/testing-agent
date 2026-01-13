"""
Test GPT-5-Nano-2025-08-07 CSV Processing Capability

This test verifies if the GPT-5-Nano model can process CSV files and extract
questions related to Artificial Intelligence, including UI Conditions and 
relevant information from Hammer configuration files.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from openai import OpenAI

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_gpt5_nano_csv_processing():
    """
    Test if GPT-5-Nano-2025-08-07 can process CSV files.
    
    This test:
    1. Loads the hammer_western_complete.csv file
    2. Sends it as a file to the model
    3. Asks for questions related to Artificial Intelligence with UI Conditions
    """
    
    # Initialize OpenAI client (uses OPENAI_API_KEY from environment)
    client = OpenAI()
    
    # Path to the CSV file
    csv_path = Path(__file__).parent / "hammer" / "hammer_western_complete.csv"
    
    if not csv_path.exists():
        print(f"❌ CSV file not found at: {csv_path}")
        return False
    
    print(f"📄 Loading CSV file: {csv_path}")
    print(f"   File size: {csv_path.stat().st_size / 1024:.2f} KB")
    
    try:
        # Read CSV content
        with open(csv_path, 'r', encoding='utf-8') as f:
            csv_content = f.read()
        
        # Truncate if too large (token limits)
        max_chars = 100000  # ~25k tokens approximately
        if len(csv_content) > max_chars:
            print(f"   ⚠️ File too large ({len(csv_content)} chars), truncating to {max_chars} chars")
            csv_content = csv_content[:max_chars]
        
        print(f"\n🤖 Sending request to gpt-5-nano-2025-08-07...")
        print("=" * 60)
        
        # Create the chat completion with file content
        response = client.chat.completions.create(
            model="gpt-5-nano-2025-08-07",
            messages=[
                {
                    "role": "system",
                    "content": """You are a Hammer configuration analyst. Analyze CSV data from Graphite Connect/HICX platform configurations.
                    
Your task is to identify questions related to Artificial Intelligence (AI) including:
- Questions that mention AI, machine learning, or artificial intelligence
- Questions about AI-related data handling
- Questions with AI-related UI Conditions

For each question found, provide:
1. Question ID
2. Label (question text)
3. UI Condition (if present)
4. Relevant metadata (Group ID, Answer Key, etc.)"""
                },
                {
                    "role": "user",
                    "content": f"""Please analyze this CSV file content and find all questions related to Artificial Intelligence.

For each AI-related question, provide:
- Question ID
- Label (the actual question text)  
- UI Condition
- Any relevant information

CSV CONTENT:
{csv_content}

Please identify questions that:
1. Contain "AI" or "Artificial Intelligence" in the label or ID
2. Have AI-related UI conditions
3. Are about machine learning, automation, or AI data processing

Format your response with clear sections for each question found."""
                }
            ]
        )
        
        # Print the response
        result = response.choices[0].message.content
        print(f"\n📊 GPT-5-Nano Response:")
        print("-" * 60)
        print(result)
        print("-" * 60)
        
        # Check token usage
        usage = response.usage
        print(f"\n📈 Token Usage:")
        print(f"   Prompt tokens: {usage.prompt_tokens}")
        print(f"   Completion tokens: {usage.completion_tokens}")
        print(f"   Total tokens: {usage.total_tokens}")
        
        print("\n✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        return False


def test_gpt5_nano_with_file_upload():
    """
    Alternative test using OpenAI Files API for larger files.
    """
    client = OpenAI()
    csv_path = Path(__file__).parent / "hammer" / "hammer_western_complete.csv"
    
    print(f"\n🔄 Testing file upload approach...")
    print("=" * 60)
    
    try:
        # Upload the file
        with open(csv_path, 'rb') as f:
            file_response = client.files.create(
                file=f,
                purpose="assistants"  # or "user_data" depending on API support
            )
        
        print(f"   File uploaded: {file_response.id}")
        
        # Note: If this model supports file references, use them
        # Otherwise, this will raise an error indicating lack of support
        response = client.chat.completions.create(
            model="gpt-5-nano-2025-08-07",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please find questions related to Artificial Intelligence in this CSV file, including their UI Conditions and relevant information."
                        },
                        {
                            "type": "file",
                            "file": {"file_id": file_response.id}
                        }
                    ]
                }
            ]
        )
        
        print(f"\n📊 Response with file upload:")
        print(response.choices[0].message.content)
        
        # Cleanup
        client.files.delete(file_response.id)
        print(f"   File deleted: {file_response.id}")
        
        return True
        
    except Exception as e:
        print(f"\n⚠️ File upload method not supported or failed:")
        print(f"   {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 GPT-5-Nano-2025-08-07 CSV Processing Test")
    print("=" * 70)
    
    # Check for OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY environment variable not set!")
        print("   Please set it before running this test:")
        print("   $env:OPENAI_API_KEY = 'your-api-key'")
        sys.exit(1)
    
    print(f"\n🔑 API Key detected: {os.environ['OPENAI_API_KEY'][:8]}...")
    
    # Run primary test (inline content)
    print("\n" + "=" * 70)
    print("🔬 Test 1: Inline CSV Content")
    print("=" * 70)
    success1 = test_gpt5_nano_csv_processing()
    
    # Run secondary test (file upload)
    print("\n" + "=" * 70)
    print("🔬 Test 2: File Upload Method")
    print("=" * 70)
    success2 = test_gpt5_nano_with_file_upload()
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 Test Summary")
    print("=" * 70)
    print(f"   Inline content method: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"   File upload method:    {'✅ PASS' if success2 else '❌ FAIL'}")
    
    sys.exit(0 if (success1 or success2) else 1)
