"""Jira Cloud API Client - Ticket search by project and labels.

This module provides programmatic access to Jira Cloud REST API v3 for searching
tickets filtered by project and customer labels. Uses the official endpoint
POST /rest/api/3/search/jql which is the current recommended approach.

Jira API documentation: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
"""

import os
import base64
import aiohttp
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class JiraTicket:
    """Parsed Jira ticket/issue."""
    key: str  # e.g., CCR-123
    summary: str
    status: str
    updated: datetime
    issue_type: str
    priority: Optional[str]
    assignee: Optional[str]
    labels: List[str]
    url: str  # Browse URL


class JiraClient:
    """
    Async client for Jira Cloud REST API v3.
    
    Provides methods to:
    - Search tickets by project and labels using JQL
    - Retrieve ticket details
    - Support pagination for large result sets
    
    Configuration uses environment variables from .env file.
    """
    
    # Default project for CCR (Customer Configuration Requests)
    DEFAULT_PROJECT = "CCR"
    
    def __init__(
        self,
        domain: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None
    ):
        """
        Initialize Jira client.
        
        Args:
            domain: Jira Cloud domain (default: from JIRA_DOMAIN env)
            email: User email (default: from JIRA_EMAIL env)
            api_token: API token (default: from JIRA_API env)
        """
        self.domain = domain or os.getenv("JIRA_DOMAIN", "projectgraphite.atlassian.net")
        
        # Support both formats: "email:token" or separate env vars
        jira_api = os.getenv("JIRA_API", "")
        if ":" in jira_api and not email:
            # Format: email:token
            parts = jira_api.split(":", 1)
            self.email = parts[0]
            self.api_token = parts[1]
        else:
            self.email = email or os.getenv("JIRA_EMAIL", "")
            self.api_token = api_token or jira_api
        
        self.base_url = f"https://{self.domain}/rest/api/3"
        
    def _get_auth_header(self) -> str:
        """Generate Basic Auth header for Jira API."""
        credentials = f"{self.email}:{self.api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    def _build_jql(
        self,
        project: str = DEFAULT_PROJECT,
        labels: Optional[List[str]] = None,
        additional_filters: Optional[str] = None
    ) -> str:
        """
        Build JQL query string.
        
        Args:
            project: Jira project key (default: CCR)
            labels: List of labels to filter by
            additional_filters: Extra JQL conditions to append
        
        Returns:
            JQL query string
        """
        conditions = [f'project = "{project}"']
        
        if labels:
            if len(labels) == 1:
                # Single label
                conditions.append(f'labels = "{labels[0]}"')
            else:
                # Multiple labels with IN clause
                labels_str = ", ".join(f'"{label}"' for label in labels)
                conditions.append(f"labels IN ({labels_str})")
        
        if additional_filters:
            conditions.append(additional_filters)
        
        return " AND ".join(conditions)
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make async HTTP request to Jira API."""
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Authorization": self._get_auth_header(),
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                headers=headers,
                json=json_data,
                **kwargs
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 400:
                    error = await response.json()
                    raise ValueError(f"Jira JQL Error: {error.get('errorMessages', error)}")
                elif response.status == 401:
                    raise PermissionError("Jira API: Invalid credentials (401 Unauthorized)")
                elif response.status == 403:
                    raise PermissionError("Jira API: Access forbidden (403)")
                elif response.status == 404:
                    return {"issues": [], "total": 0}
                else:
                    text = await response.text()
                    raise Exception(f"Jira API error {response.status}: {text}")
    
    def _parse_ticket(self, raw: Dict[str, Any]) -> JiraTicket:
        """Parse raw Jira issue into JiraTicket dataclass."""
        fields = raw.get("fields", {})
        
        # Parse updated date
        updated_str = fields.get("updated", "2000-01-01T00:00:00.000+0000")
        try:
            # Handle Jira date format
            updated = datetime.fromisoformat(updated_str.replace("+0000", "+00:00"))
        except ValueError:
            updated = datetime.now()
        
        return JiraTicket(
            key=raw.get("key", ""),
            summary=fields.get("summary", ""),
            status=fields.get("status", {}).get("name", "Unknown"),
            updated=updated,
            issue_type=fields.get("issuetype", {}).get("name", "Unknown"),
            priority=fields.get("priority", {}).get("name") if fields.get("priority") else None,
            assignee=fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            labels=fields.get("labels", []),
            url=f"https://{self.domain}/browse/{raw.get('key', '')}"
        )
    
    async def search_tickets(
        self,
        labels: Optional[List[str]] = None,
        project: str = DEFAULT_PROJECT,
        max_results: int = 50,
        additional_filters: Optional[str] = None
    ) -> List[JiraTicket]:
        """
        Search Jira tickets by project and labels.
        
        Args:
            labels: List of labels to filter by (e.g., ["WesternDigital"])
            project: Jira project key (default: CCR)
            max_results: Maximum number of results to return
            additional_filters: Extra JQL conditions (e.g., "status != Done")
        
        Returns:
            List of JiraTicket objects matching the criteria
        """
        jql = self._build_jql(
            project=project,
            labels=labels,
            additional_filters=additional_filters
        )
        
        print(f"🔍 Jira: Searching with JQL: {jql}")
        
        # Use POST /search/jql for better compatibility (no URL length limits)
        payload = {
            "jql": jql,
            "fields": [
                "summary",
                "status",
                "updated",
                "labels",
                "issuetype",
                "assignee",
                "priority"
            ],
            "maxResults": max_results
        }
        
        try:
            # Try new POST /search/jql endpoint first (recommended)
            try:
                result = await self._request("POST", "/search/jql", json_data=payload)
            except Exception as e:
                # Fallback to classic GET /search if /search/jql not available
                print(f"⚠️ Jira: /search/jql failed ({e}), trying classic /search...")
                from urllib.parse import urlencode
                query_params = urlencode({
                    "jql": jql,
                    "fields": "summary,status,updated,labels,issuetype,assignee,priority",
                    "maxResults": max_results
                })
                result = await self._request("GET", f"/search?{query_params}")
            
            issues = result.get("issues", [])
            total = result.get("total", len(issues))
            
            print(f"📋 Jira: Found {total} tickets (returning {len(issues)})")
            
            return [self._parse_ticket(issue) for issue in issues]
            
        except ValueError as e:
            print(f"⚠️ Jira: Query error - {e}")
            return []
        except PermissionError as e:
            print(f"🔒 Jira: Authentication error - {e}")
            raise
        except Exception as e:
            print(f"❌ Jira: Request failed - {e}")
            raise
    
    async def get_tickets_for_customer(
        self,
        customer_label: str,
        include_closed: bool = False
    ) -> List[JiraTicket]:
        """
        Get all tickets for a specific customer.
        
        Convenience method that searches CCR project with customer label.
        
        Args:
            customer_label: Customer label (e.g., "WesternDigital")
            include_closed: Whether to include closed/done tickets
        
        Returns:
            List of JiraTicket objects for the customer
        """
        additional_filters = None if include_closed else 'status != "Done"'
        
        return await self.search_tickets(
            labels=[customer_label],
            additional_filters=additional_filters
        )
    
    async def test_connection(self) -> bool:
        """
        Test the Jira API connection.
        
        Returns:
            True if connection is successful
        """
        try:
            # Simple search to test connection
            result = await self._request(
                "POST",
                "/search/jql",
                json_data={"jql": "project = CCR", "maxResults": 1}
            )
            print(f"✅ Jira: Connection successful! Project CCR has {result.get('total', 0)} total tickets.")
            return True
        except Exception as e:
            print(f"❌ Jira: Connection failed - {e}")
            return False


# Singleton instance
_client: Optional[JiraClient] = None


def get_jira_client() -> JiraClient:
    """Get the singleton JiraClient instance."""
    global _client
    if _client is None:
        _client = JiraClient()
    return _client


async def search_customer_tickets(
    customer_label: str,
    include_closed: bool = False
) -> List[JiraTicket]:
    """
    Convenience function to search tickets for a customer.
    
    This is the main entry point for the agent to use.
    
    Args:
        customer_label: Customer label in Jira (e.g., "WesternDigital")
        include_closed: Whether to include closed tickets
    
    Returns:
        List of JiraTicket objects
    """
    client = get_jira_client()
    return await client.get_tickets_for_customer(customer_label, include_closed)


# ==================== JIRA LABEL MATCHING ====================

import json
from pathlib import Path

# Load labels from JSON file
_JIRA_LABELS: Optional[List[str]] = None

def _load_jira_labels() -> List[str]:
    """Load Jira labels from JSON file."""
    global _JIRA_LABELS
    if _JIRA_LABELS is None:
        labels_file = Path(__file__).parent.parent / "jira_labels.json"
        try:
            with open(labels_file, "r") as f:
                _JIRA_LABELS = json.load(f)
            print(f"[JIRA] Loaded {len(_JIRA_LABELS)} labels from jira_labels.json")
        except Exception as e:
            print(f"[JIRA] Warning: Could not load labels file: {e}")
            _JIRA_LABELS = []
    return _JIRA_LABELS


def match_company_to_label(company_name: str) -> Optional[str]:
    """
    Match a company name to a Jira label using fuzzy matching.
    
    Matching strategy (in order):
    1. Exact match (case-insensitive)
    2. Normalized match (remove spaces, special chars)
    3. Partial match (company name contains label or vice versa)
    
    Args:
        company_name: Company name from hammer (e.g., "Western Digital")
        
    Returns:
        Matching Jira label or None if no match found
        
    Examples:
        "Western Digital" -> "WesternDigital"
        "Adobe" -> "Adobe"
        "Palo Alto Networks" -> "PaloAlto"
    """
    labels = _load_jira_labels()
    
    if not company_name or not labels:
        return None
    
    company_lower = company_name.lower().strip()
    company_normalized = "".join(c for c in company_lower if c.isalnum())
    
    # Strategy 1: Exact match (case-insensitive)
    for label in labels:
        if label.lower() == company_lower:
            print(f"[JIRA] Exact match: '{company_name}' -> '{label}'")
            return label
    
    # Strategy 2: Normalized match (remove spaces/special chars)
    for label in labels:
        label_normalized = "".join(c for c in label.lower() if c.isalnum())
        if label_normalized == company_normalized:
            print(f"[JIRA] Normalized match: '{company_name}' -> '{label}'")
            return label
    
    # Strategy 3: Partial match (contains)
    best_match = None
    best_score = 0
    
    for label in labels:
        label_lower = label.lower()
        label_normalized = "".join(c for c in label_lower if c.isalnum())
        
        # Check if label is contained in company name
        if label_normalized in company_normalized:
            score = len(label_normalized)
            if score > best_score:
                best_score = score
                best_match = label
        
        # Check if company name is contained in label
        elif company_normalized in label_normalized:
            score = len(company_normalized)
            if score > best_score:
                best_score = score
                best_match = label
    
    if best_match and best_score >= 6:  # Minimum 6 chars to avoid false positives
        print(f"[JIRA] Partial match: '{company_name}' -> '{best_match}' (score: {best_score})")
        return best_match
    
    print(f"[JIRA] No label match found for: '{company_name}'")
    return None


async def search_tickets_by_company(
    company_name: str,
    keywords: List[str] = None,
    max_results: int = 20,
    include_closed: bool = False
) -> List[JiraTicket]:
    """
    Search Jira tickets for a company using automatic label matching + keywords.
    
    This is the main function the agent should use when searching for past
    configuration tickets for the current company.
    
    Args:
        company_name: Company name from indexed hammer
        keywords: Optional list of keywords to narrow search
        max_results: Maximum results to return
        include_closed: Include closed/done tickets
        
    Returns:
        List of JiraTicket objects
        
    Example:
        # Find AI configuration tickets for Western Digital
        tickets = await search_tickets_by_company(
            "Western Digital",
            keywords=["AI", "configuration"]
        )
    """
    # Match company to Jira label
    label = match_company_to_label(company_name)
    
    if not label:
        print(f"[JIRA] Cannot search: no label match for '{company_name}'")
        return []
    
    # Build additional JQL filter for keywords
    additional_filter = None
    if keywords and len(keywords) > 0:
        # Use text search for keywords
        keyword_terms = " ".join(keywords)
        additional_filter = f'text ~ "{keyword_terms}"'
    
    if not include_closed:
        status_filter = 'status != "Done"'
        if additional_filter:
            additional_filter = f"{additional_filter} AND {status_filter}"
        else:
            additional_filter = status_filter
    
    client = get_jira_client()
    
    return await client.search_tickets(
        labels=[label],
        max_results=max_results,
        additional_filters=additional_filter
    )

