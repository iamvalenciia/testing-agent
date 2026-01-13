"""Test OpenAI File Analysis with GPT-5-mini - Simplified Version.

Tests if gpt-5-mini can analyze Excel data by extracting and sending
relevant content as text context.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
import pandas as pd


def test_excel_analysis():
    """Test analyzing Excel data with gpt-5-mini."""
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Read Excel file
    file_path = os.path.join(os.path.dirname(__file__), 'hammer', 'hammer_western.xlsm')
    df = pd.read_excel(file_path, sheet_name='Master Question List')
    
    print(f"Loaded Excel with {len(df)} rows")
    
    # Filter rows containing 'artificial intelligence'
    mask = df.apply(lambda row: 'artificial intelligence' in str(row).lower(), axis=1)
    ai_rows = df[mask]
    
    print(f"Found {len(ai_rows)} rows with 'Artificial Intelligence'")
    
    # Get key columns
    key_cols = ['Question Id', 'Topic', 'Sub Topic', 'UI Condition', 'Question']
    cols_exist = [c for c in key_cols if c in df.columns]
    content = ai_rows[cols_exist].to_string()
    
    print("\n" + "="*60)
    print("DATA SENT TO MODEL:")
    print("="*60)
    print(content)
    print("="*60)
    
    # Query the model
    response = client.chat.completions.create(
        model='gpt-5-mini-2025-08-07',
        messages=[{
            'role': 'user',
            'content': f'''Aqui tienes datos de un archivo Excel con preguntas relacionadas a 'Artificial Intelligence':

{content}

Por favor extrae y lista:
1. El Question ID de cada pregunta
2. El UI Condition de cada pregunta (si existe)

Responde en formato estructurado.'''
        }]
    )
    
    print("\n" + "="*60)
    print("RESPUESTA DEL MODELO GPT-5-MINI-2025-08-07:")
    print("="*60)
    print(response.choices[0].message.content)
    print("="*60)
    print(f"\nTokens: {response.usage.prompt_tokens} input + {response.usage.completion_tokens} output")
    
    return True


if __name__ == "__main__":
    test_excel_analysis()
