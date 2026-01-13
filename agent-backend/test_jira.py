"""Tests for Jira API Client - Integration tests for ticket search functionality.

These tests require valid Jira credentials in .env:
- JIRA_API: email:api_token format
- JIRA_DOMAIN: your-domain.atlassian.net

Run with: python -m pytest test_jira.py -v
Or standalone: python test_jira.py
"""

import pytest
import asyncio
import os
import sys

from tools.jira import JiraClient, JiraTicket, get_jira_client, search_customer_tickets


class TestJiraClient:
    """Test suite for JiraClient."""
    
    @pytest.fixture
    def client(self):
        """Create a JiraClient instance."""
        return JiraClient()
    
    def test_client_initialization(self, client):
        """Test that client initializes with correct defaults."""
        assert client.domain == os.getenv("JIRA_DOMAIN", "projectgraphite.atlassian.net")
        assert client.base_url.startswith("https://")
        assert "/rest/api/3" in client.base_url
    
    def test_jql_builder_single_label(self, client):
        """Test JQL query building with single label."""
        jql = client._build_jql(project="CCR", labels=["WesternDigital"])
        assert 'project = "CCR"' in jql
        assert 'labels = "WesternDigital"' in jql
    
    def test_jql_builder_multiple_labels(self, client):
        """Test JQL query building with multiple labels."""
        jql = client._build_jql(project="CCR", labels=["WesternDigital", "ACME"])
        assert 'project = "CCR"' in jql
        assert "labels IN" in jql
        assert '"WesternDigital"' in jql
        assert '"ACME"' in jql
    
    def test_jql_builder_additional_filters(self, client):
        """Test JQL query building with additional filters."""
        jql = client._build_jql(
            project="CCR",
            labels=["Test"],
            additional_filters='status != "Done"'
        )
        assert 'project = "CCR"' in jql
        assert 'status != "Done"' in jql
    
    def test_auth_header_format(self, client):
        """Test that auth header is properly formatted."""
        header = client._get_auth_header()
        assert header.startswith("Basic ")
        assert " " not in header[6:]


class TestJiraIntegration:
    """Integration tests that hit the real Jira API."""
    
    @pytest.fixture
    def skip_if_no_credentials(self):
        """Skip test if no Jira credentials configured."""
        jira_api = os.getenv("JIRA_API", "")
        if not jira_api:
            pytest.skip("JIRA_API not configured in .env")
    
    @pytest.mark.asyncio
    async def test_connection(self, skip_if_no_credentials):
        """Test that we can connect to Jira API."""
        client = get_jira_client()
        result = await client.test_connection()
        assert result is True, "Failed to connect to Jira API"
    
    @pytest.mark.asyncio
    async def test_search_western_digital_tickets(self, skip_if_no_credentials):
        """Search for WesternDigital tickets in CCR project."""
        client = get_jira_client()
        
        tickets = await client.search_tickets(
            labels=["WesternDigital"],
            project="CCR",
            max_results=10
        )
        
        print(f"\n{'='*60}")
        print(f"🎫 Found {len(tickets)} WesternDigital tickets in CCR")
        print(f"{'='*60}")
        
        for ticket in tickets:
            print(f"\n📌 {ticket.key}: {ticket.summary}")
            print(f"   Status: {ticket.status}")
            print(f"   URL: {ticket.url}")
        
        assert isinstance(tickets, list)
        
        if len(tickets) > 0:
            ticket = tickets[0]
            assert isinstance(ticket, JiraTicket)
            assert ticket.key.startswith("CCR-")
            assert ticket.summary
            assert ticket.url.startswith("https://")


# Standalone test runner
if __name__ == "__main__":
    async def run_test():
        """Quick manual test."""
        from dotenv import load_dotenv
        load_dotenv()
        
        print("🧪 Running Jira API Integration Test\n")
        
        client = JiraClient()
        
        print("1️⃣ Testing connection...")
        connected = await client.test_connection()
        
        if not connected:
            print("❌ Connection failed. Check JIRA_API credentials.")
            return
        
        print("\n2️⃣ Searching WesternDigital tickets...")
        tickets = await client.search_tickets(
            labels=["WesternDigital"],
            project="CCR",
            max_results=10
        )
        
        print(f"\n{'='*60}")
        print(f"📊 RESULTS: {len(tickets)} tickets found")
        print(f"{'='*60}")
        
        for t in tickets:
            print(f"\n🎫 {t.key}")
            print(f"   Summary: {t.summary}")
            print(f"   Status: {t.status}")
            print(f"   URL: {t.url}")
        
        print("\n✅ Test complete!")
    
    asyncio.run(run_test())
