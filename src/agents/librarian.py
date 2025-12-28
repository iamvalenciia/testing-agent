"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                              LIBRARIAN AGENT                                 ║
║                                                                              ║
║  The Librarian Agent is responsible for orchestrating the data ingestion    ║
║  pipeline. It acts as the "knowledge curator" that:                         ║
║    1. Reads data from "The Hammer" Excel file                               ║
║    2. Converts rows to semantic text chunks                                 ║
║    3. Generates embeddings using Gemini                                     ║
║    4. Stores vectors in Pinecone for retrieval                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

INGESTION WORKFLOW
==================

┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│   Excel File      │     │   Text Chunks     │     │    Embeddings     │
│  (The Hammer)     │────▶│   (All Sheets)    │────▶│   (Gemini API)    │
│   .xlsm           │     │                   │     │                   │
└───────────────────┘     └───────────────────┘     └───────────────────┘
                                                            │
                                                            ▼
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│   Query Ready     │◀────│    Pinecone       │◀────│   Vector Tuples   │
│   for RAG!        │     │    Index          │     │  (id, vec, meta)  │
└───────────────────┘     └───────────────────┘     └───────────────────┘

INGESTION MODES
===============

1. INCREMENTAL (ingest_data):
   - Upserts new data (INSERT if new, UPDATE if exists)
   - Fast for updates, but may leave orphaned vectors
   
2. CLEAN (clean_ingest):
   - Deletes ALL existing vectors first
   - Inserts fresh data
   - Guarantees data consistency with source Excel
   - Recommended for full data refreshes

"""
from src.database.vector_store import PineconeService
from src.ingestion.excel_parser import ExcelParser


class LibrarianAgent:
    """
    The Librarian Agent orchestrates the complete data ingestion pipeline.
    
    This agent is responsible for:
    - Parsing Excel data from all sheets
    - Generating semantic embeddings using Gemini
    - Managing the Pinecone vector store
    - Ensuring data consistency between source and index
    
    Attributes:
        pinecone (PineconeService): Vector store service
        parser (ExcelParser): Excel file parser
        
    Example:
        >>> agent = LibrarianAgent()
        >>> count = agent.clean_ingest()  # Fresh ingestion
        >>> print(f"Ingested {count} records")
    """
    
    def __init__(self):
        """
        Initialize the Librarian Agent.
        
        Creates connections to:
        - Pinecone vector store (validates API keys, ensures index exists)
        - Excel parser (configured with file path from environment)
        """
        self.pinecone = PineconeService()
        self.parser = ExcelParser()

    def ingest_data(self, clean: bool = False) -> int:
        """
        Orchestrate the data ingestion process.
        
        ┌─────────────────────────────────────────────────────────────────┐
        │  INGESTION PROCESS                                              │
        │                                                                 │
        │  Step 1: Parse Excel                                            │
        │    └─► Read all sheets from The Hammer                          │
        │    └─► Convert each row to semantic text chunk                  │
        │    └─► Generate unique IDs: {sheet_name}_row_{index}            │
        │                                                                 │
        │  Step 2: Generate Embeddings                                    │
        │    └─► Batch texts (50 per request)                             │
        │    └─► Call Gemini gemini-embedding-001 API                     │
        │    └─► Normalize vectors to unit length                         │
        │                                                                 │
        │  Step 3: (Optional) Clean existing data                         │
        │    └─► Delete all existing vectors if clean=True                │
        │                                                                 │
        │  Step 4: Upsert to Pinecone                                     │
        │    └─► Batch upserts (100 per request)                          │
        │    └─► Each vector: (id, embedding, metadata)                   │
        └─────────────────────────────────────────────────────────────────┘
        
        Args:
            clean: If True, delete all existing vectors before inserting.
                   Recommended for full data refreshes to ensure consistency.
        
        Returns:
            int: Number of records successfully upserted
            
        Raises:
            FileNotFoundError: If The Hammer Excel file is not found
            ValueError: If API keys are not configured
        """
        print("=" * 60)
        print("LIBRARIAN AGENT: Data Ingestion Pipeline")
        print("=" * 60)
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 1: Parse Excel (All Sheets)
        # ─────────────────────────────────────────────────────────────────
        print("\n📖 Step 1: Parsing 'The Hammer' Excel file...")
        chunks = self.parser.process_for_embedding()
        
        if not chunks:
            print("⚠️  No data found in Excel. Aborting ingestion.")
            return 0
        
        print(f"✓ Found {len(chunks)} records across all sheets")
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 2: Generate Embeddings
        # ─────────────────────────────────────────────────────────────────
        print(f"\n🧠 Step 2: Generating embeddings with Gemini...")
        texts = [chunk['text'] for chunk in chunks]
        embeddings = self.pinecone.embed_documents(texts)
        
        if len(embeddings) != len(chunks):
            print(f"⚠️  Embedding count mismatch: {len(embeddings)} vs {len(chunks)}")
            return 0
        
        print(f"✓ Generated {len(embeddings)} embeddings (dimension: 1536)")
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 3: (Optional) Clean Existing Data
        # ─────────────────────────────────────────────────────────────────
        if clean:
            print(f"\n🧹 Step 3: Cleaning existing vectors...")
            deleted = self.pinecone.delete_all_vectors()
            print(f"✓ Deleted {deleted} old vectors")
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 4: Prepare and Upsert Vectors
        # ─────────────────────────────────────────────────────────────────
        print(f"\n📤 Step {'4' if clean else '3'}: Upserting vectors to Pinecone...")
        
        vectors_to_upsert = []
        for i, chunk in enumerate(chunks):
            vectors_to_upsert.append((
                chunk['id'],           # Unique ID: sheet_name_row_index
                embeddings[i],         # 1536-dim embedding vector
                chunk['metadata']      # Full row data + sheet info
            ))
        
        self.pinecone.upsert_vectors(vectors_to_upsert)
        
        # ─────────────────────────────────────────────────────────────────
        # SUMMARY
        # ─────────────────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("✅ INGESTION COMPLETE")
        print("=" * 60)
        stats = self.pinecone.get_index_stats()
        print(f"   Records ingested: {len(vectors_to_upsert)}")
        print(f"   Total vectors in index: {stats['total_vector_count']}")
        print(f"   Index fullness: {stats['index_fullness']:.2%}")
        
        return len(vectors_to_upsert)

    def clean_ingest(self) -> int:
        """
        Perform a CLEAN ingestion - delete all existing data first.
        
        This is the recommended method for:
        - Initial data loading
        - Full data refreshes
        - When Excel data has been restructured
        - When you want to ensure 100% consistency with source
        
        Process:
        1. Delete ALL existing vectors in Pinecone
        2. Parse ALL sheets from The Hammer
        3. Generate fresh embeddings
        4. Upsert all new vectors
        
        Returns:
            int: Number of records ingested
            
        Example:
            >>> agent = LibrarianAgent()
            >>> count = agent.clean_ingest()
            >>> print(f"Cleanly ingested {count} records")
        """
        return self.ingest_data(clean=True)

    def get_stats(self) -> dict:
        """
        Get current ingestion statistics.
        
        Returns:
            dict: Current state of the vector index including:
                - total_vector_count: Total vectors stored
                - dimension: Vector dimension
                - index_fullness: Percentage of capacity used
        """
        return self.pinecone.get_index_stats()

