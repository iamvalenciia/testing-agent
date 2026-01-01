import pandas as pd
import os
from src.config import Config


class ExcelParser:
    """
    Excel parser with sheet-specific header row configuration.
    
    Different sheets in the Hammer Excel file have headers at different rows:
    - Group Definitions: Row 4 (pandas header=3)
    - All other sheets: Row 1 (pandas header=0)
    """
    
    # Sheet-specific header row configuration (0-indexed for pandas)
    # Key: sheet name, Value: row index where headers are located
    SHEET_HEADER_ROWS = {
        "Group Definitions": 3,  # Header in row 4 (1-indexed in Excel)
        # All other sheets default to 0 (row 1 in Excel)
    }
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path or Config.HAMMER_FILE_PATH

    def load_data(self, sheet_name: str = None, header_row: int = None) -> pd.DataFrame:
        """
        Load a specific sheet from the Excel file into a DataFrame.
        
        Args:
            sheet_name: Name of the sheet to load
            header_row: Row index (0-based) to use as header. If None, uses
                       sheet-specific configuration or defaults to 0.
        """
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"The Hammer not found at: {self.file_path}")
        
        # Use provided header_row, or look up in config, or default to 0
        if header_row is None:
            header_row = self.SHEET_HEADER_ROWS.get(sheet_name, 0)
        
        df = pd.read_excel(self.file_path, sheet_name=sheet_name, header=header_row)
        return df

    def get_sheet_names(self) -> list[str]:
        """Get all sheet names from the Excel file."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"The Hammer not found at: {self.file_path}")
        
        xls = pd.ExcelFile(self.file_path)
        return xls.sheet_names

    def process_for_embedding(self) -> list[dict]:
        """
        Parse ALL sheets and convert rows to semantic text chunks.
        Returns a list of dicts: {'id': str, 'text': str, 'metadata': dict}
        Empty rows are filtered out.
        """
        chunks = []
        sheet_names = self.get_sheet_names()
        
        print(f"Processing {len(sheet_names)} sheets...")
        
        for sheet_name in sheet_names:
            sheet_chunks = self._process_sheet(sheet_name)
            print(f"  - {sheet_name}: {len(sheet_chunks)} records")
            chunks.extend(sheet_chunks)
        
        print(f"Total records from all sheets: {len(chunks)}")
        return chunks

    def _process_sheet(self, sheet_name: str) -> list[dict]:
        """
        Process a single sheet and return chunks.
        Uses sheet-specific header row configuration.
        """
        # Get the correct header row for this sheet
        header_row = self.SHEET_HEADER_ROWS.get(sheet_name, 0)
        df = self.load_data(sheet_name=sheet_name, header_row=header_row)
        chunks = []
        
        # Fill NaN to avoid parser errors
        df = df.fillna("")

        # Create a clean sheet name for IDs (replace spaces with underscores)
        clean_sheet_name = sheet_name.replace(" ", "_").lower()

        for index, row in df.iterrows():
            # Create a rich semantic string representation of the row
            # Include sheet context for better semantic understanding
            text_parts = [f"Sheet: {sheet_name}"]
            text_parts.extend([f"{col}: {val}" for col, val in row.items() if val != ""])
            text_content = ". ".join(text_parts)
            
            # Skip empty rows - Gemini embedding API rejects empty strings
            if len(text_parts) <= 1:  # Only has sheet name, no actual data
                continue
            
            # ID includes sheet name for uniqueness across sheets
            chunk_id = f"{clean_sheet_name}_row_{index}"
            
            # Calculate actual Excel row number (1-indexed)
            # header_row + 1 (for the header itself) + index + 1 (1-indexed)
            actual_excel_row = header_row + index + 2
            
            # Prepare metadata - filter out empty values and convert to serializable format
            row_dict = {
                str(k): (v if isinstance(v, (int, float, str, bool)) else str(v))
                for k, v in row.to_dict().items()
                if v != "" and v is not None
            }
            
            chunks.append({
                "id": chunk_id,
                "text": text_content,
                "metadata": {
                    "source": "hammer_excel",
                    "sheet_name": sheet_name,
                    "row_index": index,
                    "excel_row": actual_excel_row,
                    **row_dict
                }
            })
            
        return chunks

