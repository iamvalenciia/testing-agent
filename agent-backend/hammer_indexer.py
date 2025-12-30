"""
Hammer Indexer - Orchestrates the complete hammer indexing pipeline.

This service handles:
1. Clearing existing hammer data from Pinecone
2. Parsing the Excel file
3. Generating embeddings
4. Upserting to hammer-index
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pinecone_service import PineconeService, IndexType


class HammerIndexer:
    """
    Orchestrates the complete hammer file indexing pipeline.
    
    This class handles parsing Excel files and indexing their contents
    into Pinecone's hammer-index for RAG queries.
    """
    
    # Sheet-specific header row configuration (0-indexed for pandas)
    SHEET_HEADER_ROWS = {
        "Group Definitions": 3,  # Header in row 4 (1-indexed in Excel)
        # All other sheets default to 0 (row 1 in Excel)
    }
    
    # Sheets to skip (usually not useful for indexing)
    SKIP_SHEETS = [
        "README",
        "Instructions", 
        "Template",
        "_xlnm",  # Excel internal sheets
    ]
    
    def __init__(self):
        """Initialize the hammer indexer with Pinecone service."""
        self.pinecone_service = PineconeService()
        print("🔧 HammerIndexer initialized")
    
    def index_hammer(self, file_path: str, clear_existing: bool = True) -> dict:
        """
        Complete hammer indexing pipeline.
        
        Args:
            file_path: Path to the .xlsm file
            clear_existing: If True, clear existing hammer data first
            
        Returns:
            dict with indexing results
        """
        print("\n" + "=" * 60)
        print("🔨 HAMMER INDEXER: Starting Indexing Pipeline")
        print("=" * 60)
        print(f"📄 File: {os.path.basename(file_path)}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Hammer file not found: {file_path}")
        
        # Step 1: Clear existing data if requested
        if clear_existing:
            print("\n🧹 Step 1: Clearing existing hammer-index data...")
            self._clear_hammer_index()
        
        # Step 2: Parse Excel file
        print("\n📖 Step 2: Parsing Excel file...")
        chunks = self._parse_hammer_file(file_path)
        
        if not chunks:
            print("⚠️ No data found in Excel. Aborting indexing.")
            return {"success": False, "error": "No data found", "records_count": 0}
        
        print(f"✓ Parsed {len(chunks)} records from Excel")
        
        # Step 3: Generate embeddings
        print("\n🧠 Step 3: Generating embeddings...")
        texts = [chunk['text'] for chunk in chunks]
        embeddings = self._generate_embeddings(texts)
        
        if len(embeddings) != len(chunks):
            print(f"⚠️ Embedding count mismatch: {len(embeddings)} vs {len(chunks)}")
            return {"success": False, "error": "Embedding mismatch", "records_count": 0}
        
        print(f"✓ Generated {len(embeddings)} embeddings")
        
        # Step 4: Upsert to Pinecone
        print("\n📤 Step 4: Upserting to hammer-index...")
        self._upsert_to_hammer_index(chunks, embeddings)
        
        # Get final stats
        stats = self._get_hammer_index_stats()
        
        # Summary
        print("\n" + "=" * 60)
        print("✅ HAMMER INDEXING COMPLETE")
        print("=" * 60)
        print(f"   Records indexed: {len(chunks)}")
        print(f"   Total vectors: {stats.get('total_vector_count', 'N/A')}")
        
        # Extract sheet names for summary
        sheets = set(chunk['metadata'].get('sheet_name', 'Unknown') for chunk in chunks)
        print(f"   Sheets indexed: {len(sheets)}")
        for sheet in sorted(sheets):
            count = sum(1 for c in chunks if c['metadata'].get('sheet_name') == sheet)
            print(f"      - {sheet}: {count} records")
        
        return {
            "success": True,
            "records_count": len(chunks),
            "sheets": list(sheets),
            "file_name": os.path.basename(file_path),
            "indexed_at": datetime.now().isoformat(),
        }
    
    def _clear_hammer_index(self):
        """Clear all vectors from hammer-index."""
        try:
            index = self.pinecone_service.get_index(IndexType.HAMMER)
            stats_before = index.describe_index_stats()
            count_before = stats_before.total_vector_count
            
            if count_before > 0:
                index.delete(delete_all=True)
                print(f"   Deleted {count_before} existing vectors")
            else:
                print("   hammer-index was already empty")
        except Exception as e:
            print(f"   Warning: Could not clear index: {e}")
    
    def _parse_hammer_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse Excel file and convert to text chunks for embedding.
        
        Args:
            file_path: Path to the .xlsm file
            
        Returns:
            List of chunks with id, text, and metadata
        """
        chunks = []
        
        try:
            # Get sheet names
            xls = pd.ExcelFile(file_path)
            sheet_names = xls.sheet_names
            
            print(f"   Found {len(sheet_names)} sheets")
            
            for sheet_name in sheet_names:
                # Skip certain sheets
                if any(skip in sheet_name for skip in self.SKIP_SHEETS):
                    print(f"   Skipping sheet: {sheet_name}")
                    continue
                
                try:
                    sheet_chunks = self._parse_sheet(file_path, sheet_name)
                    print(f"   - {sheet_name}: {len(sheet_chunks)} records")
                    chunks.extend(sheet_chunks)
                except Exception as e:
                    print(f"   ⚠️ Error parsing {sheet_name}: {e}")
                    continue
            
        except Exception as e:
            print(f"❌ Error reading Excel file: {e}")
            raise
        
        return chunks
    
    def _parse_sheet(self, file_path: str, sheet_name: str) -> List[Dict[str, Any]]:
        """Parse a single sheet and return chunks."""
        # Get header row for this sheet
        header_row = self.SHEET_HEADER_ROWS.get(sheet_name, 0)
        
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
        df = df.fillna("")  # Replace NaN with empty string
        
        chunks = []
        clean_sheet_name = sheet_name.replace(" ", "_").lower()
        
        for index, row in df.iterrows():
            # Create semantic text representation
            text_parts = [f"Sheet: {sheet_name}"]
            text_parts.extend([f"{col}: {val}" for col, val in row.items() if val != ""])
            text_content = ". ".join(text_parts)
            
            # Skip empty rows
            if len(text_parts) <= 1:
                continue
            
            # Unique ID
            chunk_id = f"hammer_{clean_sheet_name}_row_{index}"
            
            # Prepare metadata (filter out empty values)
            row_dict = {}
            for k, v in row.to_dict().items():
                if v != "" and v is not None:
                    if isinstance(v, (int, float, str, bool)):
                        row_dict[str(k)] = v
                    else:
                        row_dict[str(k)] = str(v)
            
            chunks.append({
                "id": chunk_id,
                "text": text_content,
                "metadata": {
                    "source": "hammer_excel",
                    "sheet_name": sheet_name,
                    "row_index": index,
                    "excel_row": header_row + index + 2,
                    "indexed_at": datetime.now().isoformat(),
                    **row_dict
                }
            })
        
        return chunks
    
    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Gemini embedding API (768-dim)."""
        from screenshot_embedder import get_embedder
        
        embedder = get_embedder()
        all_embeddings = []
        batch_size = 50  # Process in batches
        
        total_batches = (len(texts) - 1) // batch_size + 1
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            print(f"   Embedding batch {batch_num}/{total_batches} using Gemini...")
            
            try:
                for text in batch:
                    # Use Gemini embedder for each text
                    embedding = embedder.embed_query(text)
                    all_embeddings.append(embedding)
                    
            except Exception as e:
                print(f"   ⚠️ Error in batch {batch_num}: {e}")
                # Add zero vectors for failed embeddings (768-dim for Gemini)
                for _ in batch:
                    all_embeddings.append([0.0] * 768)
        
        return all_embeddings
    
    def _upsert_to_hammer_index(self, chunks: List[Dict], embeddings: List[List[float]]):
        """Upsert vectors to hammer-index."""
        index = self.pinecone_service.get_index(IndexType.HAMMER)
        
        batch_size = 100
        total_batches = (len(chunks) - 1) // batch_size + 1
        
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            vectors = []
            for chunk, embedding in zip(batch_chunks, batch_embeddings):
                vectors.append({
                    "id": chunk["id"],
                    "values": embedding,
                    "metadata": chunk["metadata"]
                })
            
            index.upsert(vectors=vectors)
            print(f"   Upserted batch {batch_num}/{total_batches} ({len(vectors)} vectors)")
    
    def _get_hammer_index_stats(self) -> dict:
        """Get stats for hammer-index."""
        try:
            index = self.pinecone_service.get_index(IndexType.HAMMER)
            stats = index.describe_index_stats()
            return {
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension,
            }
        except Exception as e:
            print(f"   Warning: Could not get stats: {e}")
            return {}


# Singleton instance
_indexer: Optional[HammerIndexer] = None

def get_hammer_indexer() -> HammerIndexer:
    """Get the singleton HammerIndexer instance."""
    global _indexer
    if _indexer is None:
        _indexer = HammerIndexer()
    return _indexer


if __name__ == "__main__":
    # Test with command line argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        indexer = HammerIndexer()
        result = indexer.index_hammer(file_path)
        print(f"\nResult: {json.dumps(result, indent=2)}")
    else:
        print("Usage: python hammer_indexer.py <path_to_hammer.xlsm>")
