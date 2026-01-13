"""
Hammer Query Service - Parameterized SQL queries on DuckDB.

Provides safe, parameterized queries for relational searches on hammer data:
- Find references by ID/Answer Key
- Find rows by UI condition
- Find related rows by text pattern

NO raw SQL execution - all queries are parameterized to prevent injection.
"""
import duckdb
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class HammerSearchResult:
    """Result from a hammer query."""
    sheet_name: str
    excel_row: int
    text: str
    metadata: Dict[str, Any]
    match_type: str  # 'exact', 'contains', 'reference'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sheet_name": self.sheet_name,
            "excel_row": self.excel_row,
            "text": self.text[:500] if self.text else "",  # Truncate for display
            "metadata": self.metadata,
            "match_type": self.match_type
        }


class HammerQueryService:
    """
    Service for executing parameterized SQL queries on hammer DuckDB data.
    
    This service keeps the DuckDB connection alive from ETL and provides
    safe, parameterized query methods for the agent to use.
    
    Security:
    - NO raw SQL execution allowed
    - All queries use parameterized binding
    - Input is sanitized
    """
    
    def __init__(self, db_connection: Optional[duckdb.DuckDBPyConnection] = None):
        """
        Initialize the query service.
        
        Args:
            db_connection: Optional existing DuckDB connection from ETL
        """
        self._db = db_connection
        self._table_names: List[str] = []
        
    def set_connection(self, db_connection: duckdb.DuckDBPyConnection, table_names: List[str] = None):
        """
        Set the DuckDB connection (called after ETL completes).
        
        Args:
            db_connection: Active DuckDB connection with loaded data
            table_names: List of table names created during ETL
        """
        self._db = db_connection
        self._table_names = table_names or []
        print(f"[QUERY] Connection set with {len(self._table_names)} tables")
    
    def is_ready(self) -> bool:
        """Check if the service is ready for queries."""
        return self._db is not None and len(self._table_names) > 0
    
    def _sanitize_input(self, value: str) -> str:
        """Sanitize input to prevent injection (additional safety layer)."""
        if not value:
            return ""
        # Remove or escape dangerous characters
        # Note: DuckDB's parameterized queries already handle this,
        # but this is an extra safety layer
        return value.replace("'", "''").replace(";", "").replace("--", "")
    
    def find_references_by_id(self, answer_key: str, limit: int = 50) -> List[HammerSearchResult]:
        """
        Find all rows that reference a specific Answer Key or ID.
        
        This is the "Impact Analysis" query - finds all rows that depend on
        or reference a specific configuration key.
        
        Args:
            answer_key: The Answer Key or ID to search for (e.g., "Compliance_AI_FINAL_SOT")
            limit: Maximum results to return
            
        Returns:
            List of HammerSearchResult with matching rows
        """
        if not self.is_ready():
            print("[QUERY] Service not ready - no data loaded")
            return []
        
        answer_key = self._sanitize_input(answer_key)
        results = []
        
        for table_name in self._table_names:
            try:
                # Search in all text columns for the answer_key
                query = f"""
                    SELECT * FROM {table_name}
                    WHERE text LIKE ? OR text LIKE ?
                    LIMIT ?
                """
                
                # Use wildcards for contains search
                pattern = f"%{answer_key}%"
                rows = self._db.execute(query, [pattern, pattern, limit]).fetchall()
                
                # Get column names
                columns = [desc[0] for desc in self._db.description]
                
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    results.append(HammerSearchResult(
                        sheet_name=row_dict.get("sheet_name", table_name),
                        excel_row=row_dict.get("excel_row", 0),
                        text=row_dict.get("text", ""),
                        metadata=row_dict,
                        match_type="reference"
                    ))
                    
            except Exception as e:
                print(f"[QUERY] Error searching {table_name}: {e}")
                continue
        
        print(f"[QUERY] Found {len(results)} references to '{answer_key}'")
        return results[:limit]
    
    def find_rows_by_condition(self, ui_condition: str, limit: int = 50) -> List[HammerSearchResult]:
        """
        Find rows that match a UI condition or trigger.
        
        Searches for rows where the condition/trigger columns contain
        the specified pattern.
        
        Args:
            ui_condition: The condition to search for
            limit: Maximum results
            
        Returns:
            List of matching rows
        """
        if not self.is_ready():
            return []
        
        ui_condition = self._sanitize_input(ui_condition)
        results = []
        
        # Common condition column names in hammer files
        condition_columns = ["condition", "trigger", "prerequisite", "depends_on", "ui_condition"]
        
        for table_name in self._table_names:
            try:
                # Get table columns
                cols_query = f"SELECT * FROM {table_name} LIMIT 0"
                self._db.execute(cols_query)
                columns = [desc[0].lower() for desc in self._db.description]
                
                # Find which condition columns exist
                search_cols = [c for c in condition_columns if c in columns]
                
                if not search_cols:
                    # Fallback to text column
                    search_cols = ["text"] if "text" in columns else []
                
                for col in search_cols:
                    query = f"""
                        SELECT * FROM {table_name}
                        WHERE {col} LIKE ?
                        LIMIT ?
                    """
                    pattern = f"%{ui_condition}%"
                    rows = self._db.execute(query, [pattern, limit]).fetchall()
                    
                    # Get column names again for row parsing
                    columns = [desc[0] for desc in self._db.description]
                    
                    for row in rows:
                        row_dict = dict(zip(columns, row))
                        results.append(HammerSearchResult(
                            sheet_name=row_dict.get("sheet_name", table_name),
                            excel_row=row_dict.get("excel_row", 0),
                            text=row_dict.get("text", ""),
                            metadata=row_dict,
                            match_type="condition"
                        ))
                        
            except Exception as e:
                print(f"[QUERY] Error in condition search on {table_name}: {e}")
                continue
        
        print(f"[QUERY] Found {len(results)} rows matching condition '{ui_condition}'")
        return results[:limit]
    
    def find_related_rows(self, text_pattern: str, limit: int = 50) -> List[HammerSearchResult]:
        """
        Find rows containing a text pattern.
        
        General-purpose search across all hammer data.
        
        Args:
            text_pattern: Text to search for
            limit: Maximum results
            
        Returns:
            List of matching rows
        """
        if not self.is_ready():
            return []
        
        text_pattern = self._sanitize_input(text_pattern)
        results = []
        
        for table_name in self._table_names:
            try:
                query = f"""
                    SELECT * FROM {table_name}
                    WHERE text LIKE ?
                    LIMIT ?
                """
                pattern = f"%{text_pattern}%"
                rows = self._db.execute(query, [pattern, limit]).fetchall()
                
                columns = [desc[0] for desc in self._db.description]
                
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    results.append(HammerSearchResult(
                        sheet_name=row_dict.get("sheet_name", table_name),
                        excel_row=row_dict.get("excel_row", 0),
                        text=row_dict.get("text", ""),
                        metadata=row_dict,
                        match_type="contains"
                    ))
                    
            except Exception as e:
                print(f"[QUERY] Error in text search on {table_name}: {e}")
                continue
        
        print(f"[QUERY] Found {len(results)} rows containing '{text_pattern}'")
        return results[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded data."""
        if not self.is_ready():
            return {"ready": False, "tables": 0, "rows": 0}
        
        total_rows = 0
        table_stats = {}
        
        for table_name in self._table_names:
            try:
                count = self._db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                table_stats[table_name] = count
                total_rows += count
            except:
                pass
        
        return {
            "ready": True,
            "tables": len(self._table_names),
            "total_rows": total_rows,
            "table_stats": table_stats
        }
    
    def close(self):
        """Close the DuckDB connection."""
        if self._db:
            try:
                self._db.close()
            except:
                pass
            self._db = None
            self._table_names = []


# Singleton instance
_query_service: Optional[HammerQueryService] = None


def get_hammer_query_service() -> HammerQueryService:
    """Get the singleton HammerQueryService instance."""
    global _query_service
    if _query_service is None:
        _query_service = HammerQueryService()
    return _query_service
