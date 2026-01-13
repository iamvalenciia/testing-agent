"""
Test file for Session Service functionality.
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agent-backend'))

from session_service import SessionService, get_session_service, CompanyMetadata


class TestSessionService:
    """Test cases for SessionService."""
    
    def test_singleton(self):
        """Test that get_session_service returns singleton."""
        s1 = get_session_service()
        s2 = get_session_service()
        assert s1 is s2
    
    def test_get_user_namespace(self):
        """Test namespace generation from user_id."""
        service = SessionService()
        
        # Same user_id should always get same namespace
        ns1 = service.get_user_namespace("test@example.com")
        ns2 = service.get_user_namespace("test@example.com")
        assert ns1 == ns2
        
        # Namespace should start with user_
        assert ns1.startswith("user_")
        
        # Different users should get different namespaces
        ns3 = service.get_user_namespace("other@example.com")
        assert ns1 != ns3
    
    def test_store_and_get_metadata(self):
        """Test storing and retrieving company metadata."""
        service = SessionService()
        
        # Store metadata
        metadata = service.store_company_metadata(
            user_id="test@example.com",
            company_id="US66254",
            company_name="Western Digital",
            hammer_filename="hammer_western.xlsm",
            record_count=1500,
            jira_label="WesternDigital"
        )
        
        # Verify returned metadata
        assert metadata.company_id == "US66254"
        assert metadata.company_name == "Western Digital"
        assert metadata.jira_label == "WesternDigital"
        assert metadata.record_count == 1500
        
        # Retrieve metadata
        retrieved = service.get_company_metadata("test@example.com")
        assert retrieved is not None
        assert retrieved.company_id == "US66254"
        assert retrieved.company_name == "Western Digital"
    
    def test_clear_session(self):
        """Test clearing a user's session."""
        service = SessionService()
        
        # Store metadata first
        service.store_company_metadata(
            user_id="clear_test@example.com",
            company_id="US12345",
            company_name="Test Company",
            hammer_filename="test.xlsm"
        )
        
        # Verify it exists
        assert service.get_company_metadata("clear_test@example.com") is not None
        
        # Clear session
        result = service.clear_user_session("clear_test@example.com")
        assert result is True
        
        # Verify it's gone
        assert service.get_company_metadata("clear_test@example.com") is None
    
    def test_metadata_to_dict(self):
        """Test CompanyMetadata.to_dict() serialization."""
        metadata = CompanyMetadata(
            company_id="US66254",
            company_name="Western Digital",
            indexed_at="2026-01-05T18:00:00",
            hammer_filename="hammer.xlsm",
            jira_label="WesternDigital",
            record_count=1000
        )
        
        d = metadata.to_dict()
        assert d["company_id"] == "US66254"
        assert d["company_name"] == "Western Digital"
        assert d["jira_label"] == "WesternDigital"
        assert d["record_count"] == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
