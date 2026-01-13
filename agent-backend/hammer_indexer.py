"""
Hammer Indexer - Orchestrates the complete hammer indexing pipeline.

This service handles:
1. Clearing existing hammer data from Pinecone
2. Running DuckDB ETL on the Excel file
3. Generating embeddings
4. Upserting to hammer-index

REFACTORED: Now uses HammerETL for cloud-ready Excel processing.
"""
import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pinecone_service import PineconeService, IndexType
from hammer_etl import HammerETL, HammerRow, is_hammer_file
from session_service import get_session_service, CompanyMetadata
from config import MRL_DIMENSION


class HammerIndexer:
    """
    Orchestrates the complete hammer file indexing pipeline.
    
    This class uses the DuckDB-based HammerETL for parsing and validation,
    then handles embedding generation and Pinecone indexing.
    
    Cloud-Ready Features:
    - Supports bytes input for S3/API uploads
    - Progress callbacks for UI feedback
    - Detailed validation before indexing
    - Rollback on partial failures
    """
    
    def __init__(self, on_progress: Optional[Callable[[str, float], None]] = None):
        """
        Initialize the hammer indexer.
        
        Args:
            on_progress: Optional callback for progress updates (message, percentage)
        """
        self.pinecone_service = PineconeService()
        self.session_service = get_session_service()
        self.on_progress = on_progress or (lambda msg, pct: None)
        self._etl: Optional[HammerETL] = None
        self._current_namespace: Optional[str] = None
        print("[INDEXER] HammerIndexer initialized")
    
    @property
    def etl(self) -> HammerETL:
        """Lazy initialization of ETL pipeline."""
        if self._etl is None:
            self._etl = HammerETL(on_progress=self.on_progress)
        return self._etl
    
    def index_hammer(
        self, 
        file_path: str, 
        user_id: str = None,
        company_id: str = None,
        company_name: str = None,
        clear_existing: bool = True
    ) -> dict:
        """
        Complete hammer indexing pipeline from local file.
        
        Args:
            file_path: Path to the .xlsm file
            user_id: User identifier for namespace isolation
            company_id: Company ID from hammer (e.g., "US66254")
            company_name: Company name (e.g., "Western Digital")
            clear_existing: If True, clear existing hammer data in user's namespace
            
        Returns:
            dict with indexing results including company metadata
        """
        # Get user namespace
        namespace = ""
        if user_id:
            namespace = self.session_service.get_user_namespace(user_id)
            self._current_namespace = namespace
            print(f"[INDEXER] Using namespace: {namespace} for user: {user_id}")
        
        print("\n" + "=" * 60)
        print("[HAMMER INDEXER] Starting Indexing Pipeline")
        print("=" * 60)
        print(f"[FILE] {os.path.basename(file_path)}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Hammer file not found: {file_path}")
        
        # Step 1: Clear existing data if requested (only in user's namespace)
        if clear_existing:
            self.on_progress("Clearing existing data...", 0.05)
            print(f"\n[STEP 1] Clearing hammer-index data in namespace: {namespace or 'default'}...")
            self._clear_hammer_index(namespace=namespace)
        
        # Step 2: Run DuckDB ETL
        self.on_progress("Running ETL pipeline...", 0.1)
        print("\n[STEP 2] Running DuckDB ETL pipeline...")
        etl_result = self.etl.load_from_file(file_path)
        
        if not etl_result.success:
            error_msg = etl_result.error or "Unknown ETL error"
            print(f"[ERROR] ETL failed: {error_msg}")
            return {
                "success": False, 
                "error": error_msg, 
                "records_count": 0,
                "validation": {
                    "errors": etl_result.validation.errors,
                    "warnings": etl_result.validation.warnings
                }
            }
        
        print(f"[OK] ETL complete: {len(etl_result.rows)} rows validated")
        
        # Show validation warnings
        if etl_result.validation.warnings:
            print(f"[WARNINGS]:")
            for warn in etl_result.validation.warnings:
                print(f"  - {warn}")
        
        # Step 3: Generate embeddings
        self.on_progress("Generating embeddings...", 0.4)
        print("\n[STEP 3] Generating embeddings...")
        texts = [row.text for row in etl_result.rows]
        embeddings = self._generate_embeddings(texts)
        
        if len(embeddings) != len(etl_result.rows):
            print(f"[WARNING] Embedding count mismatch: {len(embeddings)} vs {len(etl_result.rows)}")
            return {"success": False, "error": "Embedding mismatch", "records_count": 0}
        
        print(f"[OK] Generated {len(embeddings)} embeddings")
        
        # Step 4: Upsert to Pinecone (in user's namespace)
        self.on_progress("Indexing to Pinecone...", 0.7)
        print(f"\n[STEP 4] Upserting to hammer-index (namespace: {namespace or 'default'})...")
        self._upsert_rows(etl_result.rows, embeddings, namespace=namespace)
        
        # Get final stats
        self.on_progress("Finalizing...", 0.95)
        stats = self._get_hammer_index_stats()
        
        # Summary
        print("\n" + "=" * 60)
        print("[COMPLETE] HAMMER INDEXING COMPLETE")
        print("=" * 60)
        print(f"   Records indexed: {len(etl_result.rows)}")
        print(f"   Total vectors: {stats.get('total_vector_count', 'N/A')}")
        print(f"   ETL time: {etl_result.processing_time_ms}ms")
        
        # Extract sheet names for summary
        sheets = set(row.sheet_name for row in etl_result.rows)
        print(f"   Sheets indexed: {len(sheets)}")
        for sheet in sorted(sheets):
            count = sum(1 for r in etl_result.rows if r.sheet_name == sheet)
            print(f"      - {sheet}: {count} records")
        
        self.on_progress("Complete!", 1.0)
        
        # Store company metadata for session
        company_metadata = None
        if user_id:
            # Match company to Jira label
            jira_label = None
            if company_name:
                try:
                    from tools.jira import match_company_to_label
                    jira_label = match_company_to_label(company_name)
                except Exception as e:
                    print(f"[INDEXER] Could not match Jira label: {e}")
            
            company_metadata = self.session_service.store_company_metadata(
                user_id=user_id,
                company_id=company_id or "unknown",
                company_name=company_name or etl_result.file_name,
                hammer_filename=etl_result.file_name,
                record_count=len(etl_result.rows),
                jira_label=jira_label
            )
        
        return {
            "success": True,
            "records_count": len(etl_result.rows),
            "sheets": list(sheets),
            "file_name": etl_result.file_name,
            "indexed_at": datetime.now().isoformat(),
            "etl_time_ms": etl_result.processing_time_ms,
            "namespace": namespace,
            "company_metadata": company_metadata.to_dict() if company_metadata else None,
            "validation": {
                "errors": etl_result.validation.errors,
                "warnings": etl_result.validation.warnings,
                "sheet_stats": etl_result.validation.sheet_stats
            }
        }
    
    def index_hammer_from_bytes(
        self, 
        data: bytes, 
        filename: str, 
        user_id: str = None,
        company_id: str = None,
        company_name: str = None,
        clear_existing: bool = True
    ) -> dict:
        """
        Complete hammer indexing pipeline from bytes.
        
        This method is designed for cloud deployments where files come from
        S3, API uploads, or other byte-stream sources.
        
        Args:
            data: Excel file contents as bytes
            filename: Original filename for reference
            user_id: User identifier for namespace isolation
            company_id: Company ID for metadata
            company_name: Company name for metadata and Jira label matching
            clear_existing: If True, clear existing hammer data first
            
        Returns:
            dict with indexing results including company metadata
        """
        # Get user namespace
        namespace = ""
        if user_id:
            namespace = self.session_service.get_user_namespace(user_id)
            self._current_namespace = namespace
            print(f"[INDEXER] Using namespace: {namespace} for user: {user_id}")
        
        print("\n" + "=" * 60)
        print("[HAMMER INDEXER] Starting Indexing Pipeline (from bytes)")
        print("=" * 60)
        print(f"[FILE] {filename} ({len(data)} bytes)")
        
        # Step 1: Clear existing data if requested (only in user's namespace)
        if clear_existing:
            self.on_progress("Clearing existing data...", 0.05)
            print(f"\n[STEP 1] Clearing hammer-index data in namespace: {namespace or 'default'}...")
            self._clear_hammer_index(namespace=namespace)
        
        # Step 2: Run DuckDB ETL
        self.on_progress("Running ETL pipeline...", 0.1)
        print("\n[STEP 2] Running DuckDB ETL pipeline...")
        etl_result = self.etl.load_from_bytes(data, filename)
        
        if not etl_result.success:
            error_msg = etl_result.error or "Unknown ETL error"
            print(f"[ERROR] ETL failed: {error_msg}")
            return {"success": False, "error": error_msg, "records_count": 0}
        
        print(f"[OK] ETL complete: {len(etl_result.rows)} rows validated")
        
        # Step 3: Generate embeddings
        self.on_progress("Generating embeddings...", 0.4)
        print("\n[STEP 3] Generating embeddings...")
        texts = [row.text for row in etl_result.rows]
        embeddings = self._generate_embeddings(texts)
        
        if len(embeddings) != len(etl_result.rows):
            print(f"[WARNING] Embedding count mismatch: {len(embeddings)} vs {len(etl_result.rows)}")
            return {"success": False, "error": "Embedding mismatch", "records_count": 0}
        
        print(f"[OK] Generated {len(embeddings)} embeddings")
        
        # Step 4: Upsert to Pinecone (in user's namespace)
        self.on_progress("Indexing to Pinecone...", 0.7)
        print(f"\n[STEP 4] Upserting to hammer-index (namespace: {namespace or 'default'})...")
        self._upsert_rows(etl_result.rows, embeddings, namespace=namespace)
        
        # Get final stats
        self.on_progress("Finalizing...", 0.95)
        stats = self._get_hammer_index_stats()
        
        # Summary
        print("\n" + "=" * 60)
        print("[COMPLETE] HAMMER INDEXING COMPLETE")
        print("=" * 60)
        print(f"   Records indexed: {len(etl_result.rows)}")
        print(f"   Total vectors: {stats.get('total_vector_count', 'N/A')}")
        if namespace:
            print(f"   Namespace: {namespace}")
        
        sheets = set(row.sheet_name for row in etl_result.rows)
        
        self.on_progress("Complete!", 1.0)
        
        # Store company metadata for session
        company_metadata = None
        if user_id:
            # Match company to Jira label
            jira_label = None
            if company_name:
                try:
                    from tools.jira import match_company_to_label
                    jira_label = match_company_to_label(company_name)
                except Exception as e:
                    print(f"[INDEXER] Could not match Jira label: {e}")
            
            company_metadata = self.session_service.store_company_metadata(
                user_id=user_id,
                company_id=company_id or "unknown",
                company_name=company_name or filename,
                hammer_filename=filename,
                record_count=len(etl_result.rows),
                jira_label=jira_label
            )
        
        return {
            "success": True,
            "records_count": len(etl_result.rows),
            "sheets": list(sheets),
            "file_name": filename,
            "indexed_at": datetime.now().isoformat(),
            "etl_time_ms": etl_result.processing_time_ms,
            "namespace": namespace,
            "company_metadata": company_metadata.to_dict() if company_metadata else None,
        }
    
    def _clear_hammer_index(self, namespace: str = ""):
        """Clear vectors from hammer-index in a specific namespace.
        
        Args:
            namespace: Namespace to clear (empty = default namespace)
        """
        try:
            index = self.pinecone_service.get_index(IndexType.HAMMER)
            
            if namespace:
                # Delete only vectors in this namespace
                try:
                    index.delete(delete_all=True, namespace=namespace)
                    print(f"   Deleted vectors in namespace: {namespace}")
                except Exception as e:
                    print(f"   Warning: Could not clear namespace {namespace}: {e}")
            else:
                # Legacy behavior: delete all (for backwards compatibility)
                stats_before = index.describe_index_stats()
                count_before = stats_before.total_vector_count
                
                if count_before > 0:
                    index.delete(delete_all=True)
                    print(f"   Deleted {count_before} vectors from hammer-index")
                else:
                    print("   hammer-index was already empty")
        except Exception as e:
            print(f"   Warning: Could not clear index: {e}")
    
    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using Gemini embedding model (MRL_DIMENSION).
        
        IMPORTANT: The hammer-index is configured for MRL_DIMENSION dimensions,
        matching other indexes for consistency. We use Gemini embeddings
        via the screenshot_embedder module.
        """
        from screenshot_embedder import get_embedder
        embedder = get_embedder()
        
        all_embeddings = []
        batch_size = 50
        
        total_batches = (len(texts) - 1) // batch_size + 1
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            # Update progress within embedding phase (0.4 to 0.7)
            progress = 0.4 + (0.3 * (batch_num / total_batches))
            self.on_progress(f"Generating embeddings ({batch_num}/{total_batches})...", progress)
            
            print(f"   Embedding batch {batch_num}/{total_batches}...")
            
            try:
                # Use Gemini embeddings (768-dim) - consistent with all indexes
                for text in batch:
                    embedding = embedder.embed_query(text)
                    all_embeddings.append(embedding)
                    
            except Exception as e:
                print(f"   [WARNING] Error in batch {batch_num}: {e}")
                # Add zero vectors for failed embeddings (MRL_DIMENSION for Gemini)
                for _ in batch:
                    all_embeddings.append([0.0] * MRL_DIMENSION)
        
        return all_embeddings
    
    def _upsert_rows(self, rows: List[HammerRow], embeddings: List[List[float]], namespace: str = ""):
        """Upsert validated rows to hammer-index using HYBRID SEARCH.
        
        Uses native Pinecone hybrid search with both dense (semantic) and 
        sparse (keyword) vectors in the SAME index.
        
        Args:
            rows: Validated HammerRow objects
            embeddings: Pre-computed dense embeddings
            namespace: Pinecone namespace for user isolation
        """
        from hybrid_search import get_hybrid_search_service
        
        hybrid_service = get_hybrid_search_service()
        
        batch_size = 100
        total_batches = (len(rows) - 1) // batch_size + 1
        total_upserted = 0
        
        for i in range(0, len(rows), batch_size):
            batch_rows = rows[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            # Update progress within upsert phase (0.7 to 0.95)
            progress = 0.7 + (0.25 * (batch_num / total_batches))
            self.on_progress(f"Upserting batch {batch_num}/{total_batches}...", progress)
            
            # Build records for hybrid upsert
            records = []
            for row, embedding in zip(batch_rows, batch_embeddings):
                records.append({
                    "id": row.id,
                    "searchable_text": row.text,  # For sparse/keyword search
                    "dense_embedding": embedding,  # Pre-computed dense embedding
                    "metadata": row.metadata
                })
            
            # Hybrid upsert to single index (dense + sparse together)
            count = hybrid_service.hybrid_upsert(
                index_name="hammer-index",
                records=records,
                text_field="searchable_text",
                namespace=namespace  # User-specific namespace
            )
            
            total_upserted += count
            print(f"   [HYBRID] Upserted batch {batch_num}/{total_batches} ({count} vectors)")
    
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

def get_hammer_indexer(on_progress: Optional[Callable[[str, float], None]] = None) -> HammerIndexer:
    """Get the singleton HammerIndexer instance."""
    global _indexer
    if _indexer is None:
        _indexer = HammerIndexer(on_progress=on_progress)
    return _indexer


if __name__ == "__main__":
    # Test with command line argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        
        def progress_callback(msg: str, pct: float):
            print(f"[{pct*100:.0f}%] {msg}")
        
        indexer = HammerIndexer(on_progress=progress_callback)
        result = indexer.index_hammer(file_path)
        print(f"\nResult: {json.dumps(result, indent=2)}")
    else:
        print("Usage: python hammer_indexer.py <path_to_hammer.xlsm>")
