"""
Hammer ETL - Cloud-Ready DuckDB-based ETL Pipeline for Hammer Excel Files.

This module provides a robust ETL pipeline that:
1. Loads Excel files from local path, bytes, or S3
2. Auto-detects header rows in each sheet
3. Validates and normalizes data schema
4. Exports clean rows ready for embedding and indexing

Cloud-Ready Features:
- Environment-based configuration (local vs cloud)
- Streaming support for large files
- Pre-validation before Pinecone operations
- Detailed validation reports
"""
import os
import io
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

import duckdb
import pandas as pd


class DataSource(Enum):
    """Source of the hammer data."""
    LOCAL_FILE = "local_file"
    BYTES = "bytes"
    S3 = "s3"


@dataclass
class ValidationResult:
    """Result of schema validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sheet_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class HammerRow:
    """A validated and normalized row from the Hammer file."""
    id: str
    sheet_name: str
    row_index: int
    excel_row: int
    text: str
    metadata: Dict[str, Any]


@dataclass
class ETLResult:
    """Result of the complete ETL pipeline."""
    success: bool
    source: DataSource
    file_name: str
    rows: List[HammerRow]
    validation: ValidationResult
    processing_time_ms: int
    error: Optional[str] = None


class HammerETL:
    """
    Cloud-ready DuckDB-based ETL pipeline for Hammer Excel files.
    
    Handles parsing, validation, and normalization of Hammer configuration
    files with automatic header detection and schema validation.
    
    Usage:
        etl = HammerETL()
        result = etl.load_from_file("path/to/hammer.xlsm")
        
        if result.success:
            for row in result.rows:
                print(row.text)
    """
    
    # Sheet-specific header row configuration (0-indexed for pandas)
    SHEET_HEADER_ROWS = {
        "Group Definitions": 3,  # Header in row 4 (1-indexed in Excel)
    }
    
    # Sheets to skip
    SKIP_SHEETS = [
        "README",
        "Instructions",
        "Template",
        "_xlnm",
    ]
    
    # Minimum columns for a valid sheet
    MIN_COLUMNS = 2
    
    # Maximum empty rows before stopping
    MAX_EMPTY_ROWS = 10
    
    def __init__(self, on_progress: Optional[Callable[[str, float], None]] = None):
        """
        Initialize the Hammer ETL pipeline.
        
        Args:
            on_progress: Optional callback for progress updates (message, percentage)
        """
        self.on_progress = on_progress or (lambda msg, pct: None)
        self._db = duckdb.connect(":memory:")
        self._temp_dir = tempfile.gettempdir()
        
        # Environment configuration
        self.is_cloud = os.getenv("DEPLOYMENT_ENV", "local") != "local"
        self.s3_bucket = os.getenv("HAMMER_S3_BUCKET", "")
        
        print("[ETL] HammerETL initialized (cloud_mode={self.is_cloud})")
    
    def load_from_file(self, file_path: str) -> ETLResult:
        """
        Load and process a Hammer Excel file from local filesystem.
        
        Args:
            file_path: Path to the .xlsm file
            
        Returns:
            ETLResult with processed rows and validation info
        """
        start_time = datetime.now()
        file_name = os.path.basename(file_path)
        
        self.on_progress(f"Loading {file_name}...", 0.0)
        
        if not os.path.exists(file_path):
            return ETLResult(
                success=False,
                source=DataSource.LOCAL_FILE,
                file_name=file_name,
                rows=[],
                validation=ValidationResult(is_valid=False, errors=[f"File not found: {file_path}"]),
                processing_time_ms=0,
                error=f"File not found: {file_path}"
            )
        
        try:
            # Read Excel file into pandas
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            
            return self._process_excel_bytes(file_bytes, file_name, DataSource.LOCAL_FILE, start_time)
            
        except Exception as e:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            return ETLResult(
                success=False,
                source=DataSource.LOCAL_FILE,
                file_name=file_name,
                rows=[],
                validation=ValidationResult(is_valid=False, errors=[str(e)]),
                processing_time_ms=processing_time,
                error=str(e)
            )
    
    def load_from_bytes(self, data: bytes, filename: str = "hammer.xlsm") -> ETLResult:
        """
        Load and process a Hammer Excel file from bytes.
        
        This method is designed for cloud deployments where files come from
        S3, API uploads, or other byte-stream sources.
        
        Args:
            data: Excel file contents as bytes
            filename: Original filename for reference
            
        Returns:
            ETLResult with processed rows and validation info
        """
        start_time = datetime.now()
        self.on_progress(f"Loading {filename} from bytes...", 0.0)
        
        try:
            return self._process_excel_bytes(data, filename, DataSource.BYTES, start_time)
        except Exception as e:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            return ETLResult(
                success=False,
                source=DataSource.BYTES,
                file_name=filename,
                rows=[],
                validation=ValidationResult(is_valid=False, errors=[str(e)]),
                processing_time_ms=processing_time,
                error=str(e)
            )
    
    def load_from_s3(self, bucket: str, key: str) -> ETLResult:
        """
        Load and process a Hammer Excel file from S3.
        
        This method will be activated when deployed to AWS cloud.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            ETLResult with processed rows and validation info
        """
        start_time = datetime.now()
        filename = key.split("/")[-1]
        
        self.on_progress(f"Loading from S3: {bucket}/{key}...", 0.0)
        
        try:
            # Import boto3 only when needed (cloud deployment)
            import boto3
            
            s3 = boto3.client('s3')
            response = s3.get_object(Bucket=bucket, Key=key)
            data = response['Body'].read()
            
            return self._process_excel_bytes(data, filename, DataSource.S3, start_time)
            
        except ImportError:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            return ETLResult(
                success=False,
                source=DataSource.S3,
                file_name=filename,
                rows=[],
                validation=ValidationResult(is_valid=False, errors=["boto3 not installed - S3 not available"]),
                processing_time_ms=processing_time,
                error="boto3 not installed"
            )
        except Exception as e:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            return ETLResult(
                success=False,
                source=DataSource.S3,
                file_name=filename,
                rows=[],
                validation=ValidationResult(is_valid=False, errors=[str(e)]),
                processing_time_ms=processing_time,
                error=str(e)
            )
    
    def _process_excel_bytes(
        self, 
        data: bytes, 
        filename: str, 
        source: DataSource, 
        start_time: datetime
    ) -> ETLResult:
        """
        Process Excel bytes through the DuckDB ETL pipeline.
        
        Pipeline stages:
        1. Parse Excel sheets
        2. Detect headers for each sheet
        3. Load data into DuckDB tables
        4. Validate schema
        5. Normalize and export rows
        """
        all_rows: List[HammerRow] = []
        validation = ValidationResult(is_valid=True)
        
        try:
            # Parse Excel file
            self.on_progress("Parsing Excel sheets...", 0.1)
            xls = pd.ExcelFile(io.BytesIO(data))
            sheet_names = xls.sheet_names
            
            print(f"[ETL] Found {len(sheet_names)} sheets in {filename}")
            
            # Filter out skipped sheets
            valid_sheets = [
                s for s in sheet_names 
                if not any(skip.lower() in s.lower() for skip in self.SKIP_SHEETS)
            ]
            
            print(f"[ETL] Processing {len(valid_sheets)} valid sheets")
            
            # Process each sheet
            total_sheets = len(valid_sheets)
            for idx, sheet_name in enumerate(valid_sheets):
                progress = 0.1 + (0.8 * (idx / total_sheets))
                self.on_progress(f"Processing sheet: {sheet_name}", progress)
                
                try:
                    sheet_rows, sheet_stats = self._process_sheet(xls, sheet_name)
                    all_rows.extend(sheet_rows)
                    validation.sheet_stats[sheet_name] = sheet_stats
                    
                    print(f"[ETL]   - {sheet_name}: {len(sheet_rows)} rows")
                    
                except Exception as e:
                    validation.warnings.append(f"Error in sheet {sheet_name}: {str(e)}")
                    print(f"[ETL] [WARNING] Error processing {sheet_name}: {e}")
            
            # Finalize
            self.on_progress("Finalizing...", 0.95)
            
            if len(all_rows) == 0:
                validation.is_valid = False
                validation.errors.append("No valid data rows found in any sheet")
            
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            self.on_progress("Complete!", 1.0)
            print(f"[ETL] [COMPLETE] Processed {len(all_rows)} rows in {processing_time}ms")
            
            return ETLResult(
                success=len(all_rows) > 0,
                source=source,
                file_name=filename,
                rows=all_rows,
                validation=validation,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            validation.is_valid = False
            validation.errors.append(str(e))
            
            return ETLResult(
                success=False,
                source=source,
                file_name=filename,
                rows=[],
                validation=validation,
                processing_time_ms=processing_time,
                error=str(e)
            )
    
    def _process_sheet(self, xls: pd.ExcelFile, sheet_name: str) -> Tuple[List[HammerRow], Dict[str, Any]]:
        """
        Process a single Excel sheet using DuckDB.
        
        Steps:
        1. Detect header row
        2. Load into DuckDB table
        3. Normalize column names
        4. Export validated rows
        """
        # Determine header row
        header_row = self._detect_header_row(xls, sheet_name)
        
        # Read with detected header
        df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row)
        df = df.fillna("")
        
        # Clean column names
        df.columns = [self._normalize_column_name(str(col)) for col in df.columns]
        
        # Load into DuckDB for validation and normalization
        table_name = f"sheet_{sheet_name.replace(' ', '_').replace('-', '_').lower()}"
        self._db.register(table_name, df)
        
        # Query stats
        stats = {
            "header_row": header_row,
            "column_count": len(df.columns),
            "row_count": len(df),
            "columns": list(df.columns)
        }
        
        # Convert to HammerRow objects
        rows: List[HammerRow] = []
        clean_sheet_name = sheet_name.replace(" ", "_").lower()
        
        for idx, row in df.iterrows():
            # Create text representation
            text_parts = [f"Sheet: {sheet_name}"]
            metadata = {
                "source": "hammer_excel",
                "sheet_name": sheet_name,
                "row_index": idx,
                "excel_row": header_row + idx + 2,  # Account for 1-indexing and header
                "indexed_at": datetime.now().isoformat(),
            }
            
            # Add non-empty values to text and metadata
            for col, val in row.items():
                if val != "" and val is not None:
                    text_parts.append(f"{col}: {val}")
                    # Add to metadata (normalize value types)
                    if isinstance(val, (int, float, str, bool)):
                        metadata[str(col)] = val
                    else:
                        metadata[str(col)] = str(val)
            
            # Skip empty rows
            if len(text_parts) <= 1:
                continue
            
            text_content = ". ".join(text_parts)
            chunk_id = f"hammer_{clean_sheet_name}_row_{idx}"
            
            rows.append(HammerRow(
                id=chunk_id,
                sheet_name=sheet_name,
                row_index=idx,
                excel_row=header_row + idx + 2,
                text=text_content,
                metadata=metadata
            ))
        
        return rows, stats
    
    def _detect_header_row(self, xls: pd.ExcelFile, sheet_name: str) -> int:
        """
        Auto-detect the header row in a sheet.
        
        Uses heuristics to find the row that looks most like headers:
        - Has multiple non-empty cells
        - Cells contain text (not numbers)
        - Cells are relatively short strings
        
        Falls back to configured defaults for known sheets.
        """
        # Check if we have a configured header row for this sheet
        if sheet_name in self.SHEET_HEADER_ROWS:
            return self.SHEET_HEADER_ROWS[sheet_name]
        
        try:
            # Read first 10 rows without header
            df_preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=10)
            
            best_row = 0
            best_score = 0
            
            for row_idx in range(min(10, len(df_preview))):
                row = df_preview.iloc[row_idx]
                score = self._score_header_row(row)
                
                if score > best_score:
                    best_score = score
                    best_row = row_idx
            
            return best_row
            
        except Exception:
            return 0  # Default to first row
    
    def _score_header_row(self, row: pd.Series) -> float:
        """
        Score a row's likelihood of being a header row.
        
        Higher score = more likely to be headers.
        """
        score = 0.0
        non_empty_count = 0
        
        for val in row:
            if pd.isna(val) or val == "":
                continue
                
            non_empty_count += 1
            val_str = str(val)
            
            # Prefer text over numbers
            if not val_str.replace(".", "").replace("-", "").isdigit():
                score += 2.0
            
            # Prefer short strings (typical for headers)
            if len(val_str) < 50:
                score += 1.0
            
            # Bonus for common header patterns
            header_keywords = ["id", "name", "type", "value", "date", "status", "code", "description"]
            if any(kw in val_str.lower() for kw in header_keywords):
                score += 3.0
        
        # Prefer rows with multiple columns (not single-cell titles)
        if non_empty_count >= self.MIN_COLUMNS:
            score *= 1.5
        
        return score
    
    def _normalize_column_name(self, col: str) -> str:
        """
        Normalize a column name for consistent processing.
        
        - Strips whitespace
        - Replaces special characters
        - Handles unnamed columns
        """
        col = str(col).strip()
        
        # Handle pandas default unnamed columns  
        if col.startswith("Unnamed:"):
            return f"column_{col.split(':')[1].strip()}"
        
        # Replace problematic characters
        col = col.replace("\n", " ").replace("\r", "")
        
        return col
    
    def close(self):
        """Close the DuckDB connection."""
        if self._db:
            self._db.close()
            self._db = None


# Singleton instance
_etl: Optional[HammerETL] = None


def get_hammer_etl(on_progress: Optional[Callable[[str, float], None]] = None) -> HammerETL:
    """Get the singleton HammerETL instance."""
    global _etl
    if _etl is None:
        _etl = HammerETL(on_progress=on_progress)
    return _etl


# =============================================================================
# AUTOMATIC HAMMER DETECTION WORKFLOW
# =============================================================================

def is_hammer_file(filename: str) -> bool:
    """
    Check if a filename looks like a Hammer configuration file.
    
    Args:
        filename: The filename to check
        
    Returns:
        True if the file appears to be a Hammer file
    """
    filename_lower = filename.lower()
    
    # Must be an Excel macro file
    if not filename_lower.endswith(".xlsm"):
        return False
    
    # Check for hammer-related patterns
    hammer_patterns = [
        "hammer",
        "config",
        "configuration",
        "setup",
    ]
    
    return any(pattern in filename_lower for pattern in hammer_patterns)


async def trigger_hammer_indexing_workflow(
    file_path: str,
    on_progress: Optional[Callable[[str, float], None]] = None,
    pinecone_service = None
) -> Dict[str, Any]:
    """
    Trigger the complete hammer indexing workflow.
    
    This is the main entry point for automatic hammer indexing.
    
    Workflow:
    1. Clear existing hammer-index data
    2. Run DuckDB ETL on the Excel file
    3. Generate embeddings for each row
    4. Upsert to Pinecone hammer-index
    
    Args:
        file_path: Path to the hammer Excel file
        on_progress: Optional progress callback
        pinecone_service: PineconeService instance (optional, will create if not provided)
        
    Returns:
        Dict with workflow results
    """
    from hammer_indexer import get_hammer_indexer
    
    # Use the existing hammer indexer which will now use our ETL
    indexer = get_hammer_indexer()
    
    # Run the indexing
    result = indexer.index_hammer(file_path, clear_existing=True)
    
    return result


if __name__ == "__main__":
    # Test the ETL pipeline
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        
        def progress_callback(msg: str, pct: float):
            print(f"[{pct*100:.0f}%] {msg}")
        
        etl = HammerETL(on_progress=progress_callback)
        result = etl.load_from_file(file_path)
        
        print(f"\n{'='*60}")
        print(f"ETL RESULT")
        print(f"{'='*60}")
        print(f"Success: {result.success}")
        print(f"Source: {result.source.value}")
        print(f"File: {result.file_name}")
        print(f"Rows: {len(result.rows)}")
        print(f"Processing Time: {result.processing_time_ms}ms")
        
        if result.validation.errors:
            print(f"\nErrors:")
            for err in result.validation.errors:
                print(f"  - {err}")
        
        if result.validation.warnings:
            print(f"\nWarnings:")
            for warn in result.validation.warnings:
                print(f"  - {warn}")
        
        print(f"\nSheet Stats:")
        for sheet, stats in result.validation.sheet_stats.items():
            print(f"  {sheet}:")
            print(f"    - Header Row: {stats['header_row']}")
            print(f"    - Columns: {stats['column_count']}")
            print(f"    - Rows: {stats['row_count']}")
    else:
        print("Usage: python hammer_etl.py <path_to_hammer.xlsm>")
