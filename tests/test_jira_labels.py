"""
Test file for Jira label matching functionality.
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agent-backend'))

from tools.jira import match_company_to_label, _load_jira_labels


class TestJiraLabelMatching:
    """Test cases for company name to Jira label matching."""
    
    def test_load_labels(self):
        """Test that labels are loaded from JSON file."""
        labels = _load_jira_labels()
        assert len(labels) > 0
        assert "WesternDigital" in labels
        assert "Adobe" in labels
    
    def test_exact_match(self):
        """Test exact case-insensitive matching."""
        assert match_company_to_label("Adobe") == "Adobe"
        assert match_company_to_label("adobe") == "Adobe"
        assert match_company_to_label("ADOBE") == "Adobe"
    
    def test_normalized_match(self):
        """Test matching with spaces and special chars removed."""
        # "Western Digital" should match "WesternDigital"
        assert match_company_to_label("Western Digital") == "WesternDigital"
        assert match_company_to_label("western digital") == "WesternDigital"
        
        # "Palo Alto" should match "PaloAlto"
        assert match_company_to_label("Palo Alto") == "PaloAlto"
        
    def test_partial_match(self):
        """Test partial/fuzzy matching."""
        # Company name contains label
        result = match_company_to_label("Western Digital Technologies, Inc.")
        assert result == "WesternDigital"
        
        # Try with abbreviation patterns
        result = match_company_to_label("Air Liquide")
        assert result == "AirLiquide"
    
    def test_no_match(self):
        """Test cases where no match should be found."""
        # Use a string that won't accidentally match any valid labels
        result = match_company_to_label("XYZABC123456")
        assert result is None
        
        result = match_company_to_label("")
        assert result is None
    
    def test_known_companies(self):
        """Test key expected company name to label mappings."""
        test_cases = [
            ("Western Digital", "WesternDigital"),
            ("Adobe", "Adobe"),
            ("Vonage", "Vonage"),
            ("Dropbox", "Dropbox"),
            ("Spotify", "Spotify"),
            ("MongoDB", "MongoDB"),
            ("Datadog", "Datadog"),
            ("Intel", "Intel"),
        ]
        
        for company_name, expected_label in test_cases:
            result = match_company_to_label(company_name)
            assert result == expected_label, f"Expected {expected_label} for '{company_name}', got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
