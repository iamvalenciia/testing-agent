"""
Tests for the Hammer ETL Pipeline.

Tests cover:
- Header row detection
- Schema validation
- Data normalization
- Error handling for malformed files
- Cloud-ready patterns (bytes loading)

Run with: python test_hammer_etl.py
"""
import io
import os
import sys
import pandas as pd
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hammer_etl import (
    HammerETL, 
    HammerRow, 
    ETLResult, 
    ValidationResult, 
    DataSource,
    is_hammer_file,
)


def test_hammer_file_detection():
    """Test hammer file name detection."""
    print("\n[TEST] Testing hammer file detection...")
    
    # Should detect hammer patterns
    assert is_hammer_file("client_hammer.xlsm") is True
    assert is_hammer_file("HAMMER_CONFIG.xlsm") is True
    assert is_hammer_file("US12345_hammer_2024.xlsm") is True
    assert is_hammer_file("client_config.xlsm") is True
    
    # Should reject non-xlsm
    assert is_hammer_file("hammer.xlsx") is False
    assert is_hammer_file("hammer.csv") is False
    
    # Should reject unrelated xlsm
    assert is_hammer_file("budget_2024.xlsm") is False
    
    print("   [OK] All file detection tests passed")


def test_load_from_bytes():
    """Test loading Excel from bytes."""
    print("\n[TEST] Testing load from bytes...")
    
    # Create sample Excel
    df = pd.DataFrame({
        "ID": ["US001", "US002", "US003"],
        "Name": ["Client A", "Client B", "Client C"],
        "Status": ["Active", "Pending", "Active"],
    })
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Clients", index=False)
    buffer.seek(0)
    
    etl = HammerETL()
    result = etl.load_from_bytes(buffer.read(), "test_hammer.xlsm")
    
    assert result.success is True, f"Expected success, got: {result.error}"
    assert result.source == DataSource.BYTES
    assert result.file_name == "test_hammer.xlsm"
    assert len(result.rows) == 3, f"Expected 3 rows, got {len(result.rows)}"
    
    # Check row structure
    row = result.rows[0]
    assert isinstance(row, HammerRow)
    assert row.sheet_name == "Clients"
    assert "Sheet: Clients" in row.text
    assert "ID: US001" in row.text
    assert row.metadata["source"] == "hammer_excel"
    
    print(f"   [OK] Loaded {len(result.rows)} rows from bytes")


def test_empty_file_handling():
    """Test handling of empty files."""
    print("\n[TEST] Testing empty file handling...")
    
    df = pd.DataFrame()
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Empty", index=False)
    buffer.seek(0)
    
    etl = HammerETL()
    result = etl.load_from_bytes(buffer.read(), "empty.xlsm")
    
    assert result.success is False
    assert len(result.validation.errors) > 0
    
    print(f"   [OK] Empty file handled correctly: {result.validation.errors}")


def test_invalid_data_handling():
    """Test handling of invalid data."""
    print("\n[TEST] Testing invalid data handling...")
    
    etl = HammerETL()
    result = etl.load_from_bytes(b"not an excel file", "invalid.xlsm")
    
    assert result.success is False
    assert result.error is not None
    
    print(f"   [OK] Invalid data handled: {result.error[:50]}...")


def test_progress_callback():
    """Test progress callback is called."""
    print("\n[TEST] Testing progress callback...")
    
    progress_calls = []
    
    def capture_progress(msg, pct):
        progress_calls.append((msg, pct))
    
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Test", index=False)
    buffer.seek(0)
    
    etl = HammerETL(on_progress=capture_progress)
    etl.load_from_bytes(buffer.read(), "test.xlsm")
    
    assert len(progress_calls) > 0
    assert progress_calls[0][1] == 0.0  # First at 0%
    assert progress_calls[-1][1] == 1.0  # Last at 100%
    
    print(f"   [OK] Progress callback called {len(progress_calls)} times")


def test_sheet_stats():
    """Test sheet statistics collection."""
    print("\n[TEST] Testing sheet stats...")
    
    df = pd.DataFrame({
        "Col1": [1, 2, 3, 4, 5],
        "Col2": ["a", "b", "c", "d", "e"],
        "Col3": [True, False, True, True, False],
    })
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Stats", index=False)
    buffer.seek(0)
    
    etl = HammerETL()
    result = etl.load_from_bytes(buffer.read(), "test.xlsm")
    
    assert "Stats" in result.validation.sheet_stats
    stats = result.validation.sheet_stats["Stats"]
    assert stats["column_count"] == 3
    assert stats["row_count"] == 5
    
    print(f"   [OK] Sheet stats: {stats}")


def test_nan_handling():
    """Test NaN value handling."""
    print("\n[TEST] Testing NaN handling...")
    
    import numpy as np
    
    # Use string IDs that won't be converted to floats
    df = pd.DataFrame({
        "ID": ["US001", "US002", "US003"],
        "Value": [100, np.nan, 300],
        "Status": ["Active", np.nan, "Pending"],
    })
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Test", index=False)
    buffer.seek(0)
    
    etl = HammerETL()
    result = etl.load_from_bytes(buffer.read(), "test.xlsm")
    
    assert result.success is True
    assert len(result.rows) == 3
    # First row should have ID and Value
    assert "ID: US001" in result.rows[0].text
    # Value might be 100 or 100.0 depending on pandas version
    assert "Value: 100" in result.rows[0].text or "Value: 100.0" in result.rows[0].text
    assert "Status: Active" in result.rows[0].text
    
    print(f"   [OK] NaN values handled correctly")


def test_cloud_readiness():
    """Test cloud-ready patterns."""
    print("\n[TEST] Testing cloud readiness...")
    
    etl = HammerETL()
    
    # Should have S3 method
    assert hasattr(etl, 'load_from_s3')
    
    # Should detect local environment by default
    assert etl.is_cloud is False
    
    # S3 should fail gracefully without boto3
    result = etl.load_from_s3("test-bucket", "test-key.xlsm")
    assert result.success is False
    assert result.source == DataSource.S3
    
    print("   [OK] Cloud-ready patterns verified")


def test_multiple_sheets():
    """Test processing multiple sheets."""
    print("\n[TEST] Testing multiple sheets...")
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        pd.DataFrame({"A": [1, 2]}).to_excel(writer, sheet_name="Sheet1", index=False)
        pd.DataFrame({"B": [3, 4, 5]}).to_excel(writer, sheet_name="Sheet2", index=False)
    buffer.seek(0)
    
    etl = HammerETL()
    result = etl.load_from_bytes(buffer.read(), "multi.xlsm")
    
    assert result.success is True
    assert len(result.validation.sheet_stats) == 2
    
    # Should have rows from both sheets
    sheet_names = set(row.sheet_name for row in result.rows)
    assert "Sheet1" in sheet_names
    assert "Sheet2" in sheet_names
    
    print(f"   [OK] Processed {len(sheet_names)} sheets with {len(result.rows)} total rows")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("HAMMER ETL TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_hammer_file_detection,
        test_load_from_bytes,
        test_empty_file_handling,
        test_invalid_data_handling,
        test_progress_callback,
        test_sheet_stats,
        test_nan_handling,
        test_cloud_readiness,
        test_multiple_sheets,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"   [FAILED] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"   [ERROR] {test.__name__}: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
