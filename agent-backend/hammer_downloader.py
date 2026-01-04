"""
Hammer Downloader - Direct API-based Hammer file download.

This service bypasses Playwright browser automation by directly calling
the Graphite API to download Hammer files. Much more reliable than
detecting .xlsm downloads in Chrome test environments.

Flow:
1. User says "download hammer from Western Digital"
2. Fuzzy match "Western Digital" → company_id "US66254"
3. GET /api/admin/tools/questions/history?filter=US66254
4. Extract _id from first (most recent) history item
5. GET /api/admin/tools/questions/history_download/{_id}
6. Save bytes and trigger HammerIndexer
"""
import os
import json
import httpx
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
from difflib import SequenceMatcher

from hammer_indexer import get_hammer_indexer


# =============================================================================
# COMPANY REGISTRY
# Add new companies here. The 'aliases' field enables fuzzy matching.
# =============================================================================
# =============================================================================
# COMPANY REGISTRY
# The companies list is now dynamically loaded from Pinecone.
# See parse_companies_from_text() below.
# =============================================================================



class HammerDownloader:
    """
    Downloads Hammer files directly via Graphite API.
    
    This is the recommended way to get Hammer files for indexing,
    as it avoids the complexity of browser automation and file
    detection in Chrome test environments.
    """
    
    # API Configuration
    BASE_URL = "https://test.projectgraphite.com"
    HISTORY_ENDPOINT = "/api/admin/tools/questions/history"
    DOWNLOAD_ENDPOINT = "/api/admin/tools/questions/history_download"
    
    def __init__(
        self, 
        auth_cookie: Optional[str] = None,
        companies: List[Dict] = None,
        on_progress: Optional[Callable[[str, float], None]] = None
    ):
        """
        Initialize the downloader.
        
        Args:
            auth_cookie: Authentication cookie for Graphite API.
                        If not provided, will try to get from browser session.
            on_progress: Optional callback for progress updates (message, percentage)
        """
        self.auth_cookie = auth_cookie or os.getenv("GRAPHITE_AUTH_COOKIE", "")
        self.on_progress = on_progress or (lambda msg, pct: None)
        self.auth_cookie = auth_cookie or os.getenv("GRAPHITE_AUTH_COOKIE", "")
        self.on_progress = on_progress or (lambda msg, pct: None)
        self.companies = companies or []
        
        if not self.companies:
            print("[DOWNLOADER] WARNING: Initialized with EMPTY companies list!")
        else:
            print(f"[DOWNLOADER] Initialized with {len(self.companies)} companies")
        
        print("[DOWNLOADER] HammerDownloader initialized")
    
    def find_company(self, query: str) -> Optional[Dict]:
        """
        Fuzzy match a company name from the registry.
        
        Args:
            query: User's input (e.g., "western", "adobe test")
            
        Returns:
            Company dict with id, company_name, aliases or None if not found
        """
        query_lower = query.lower().strip()
        
        # First, try exact alias match
        for company in self.companies:
            if query_lower in [a.lower() for a in company.get("aliases", [])]:
                print(f"[MATCH] Exact alias match: '{query}' → {company['company_name']}")
                return company
            
            # Also check exact company name match
            if query_lower == company["company_name"].lower():
                print(f"[MATCH] Exact name match: '{query}' → {company['company_name']}")
                return company
        
        # Second, try partial match on company name
        for company in self.companies:
            if query_lower in company["company_name"].lower():
                print(f"[MATCH] Partial name match: '{query}' → {company['company_name']}")
                return company
        
        # Third, try fuzzy match using SequenceMatcher
        best_match = None
        best_score = 0.0
        
        for company in self.companies:
            # Check against company name
            score = SequenceMatcher(None, query_lower, company["company_name"].lower()).ratio()
            if score > best_score:
                best_score = score
                best_match = company
            
            # Check against each alias
            for alias in company.get("aliases", []):
                score = SequenceMatcher(None, query_lower, alias.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_match = company
        
        # Require minimum 60% match for fuzzy
        if best_score >= 0.6:
            print(f"[MATCH] Fuzzy match ({best_score:.0%}): '{query}' → {best_match['company_name']}")
            return best_match
        
        print(f"[WARNING] No company match found for: '{query}'")
        return None
    
    def list_companies(self) -> List[Dict]:
        """Return all registered companies."""
        return self.companies
    
    async def get_latest_hammer_id(self, company_id: str) -> Optional[Dict]:
        """
        Call the Graphite API to get the latest hammer history for a company.
        
        Args:
            company_id: The company ID (e.g., "US66254")
            
        Returns:
            Dict with '_id', 'originalFilename', 'createdAt' or None if not found
        """
        url = f"{self.BASE_URL}{self.HISTORY_ENDPOINT}"
        params = {"filter": company_id}
        
        headers = {}
        if self.auth_cookie:
            headers["Cookie"] = self.auth_cookie
        
        self.on_progress(f"Fetching hammer history for {company_id}...", 0.1)
        print(f"[API] GET {url}?filter={company_id}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                history = data.get("history", [])
                
                if not history:
                    print(f"[WARNING] No hammer history found for {company_id}")
                    return None
                
                # Get the first (most recent) entry
                latest = history[0]
                result = {
                    "_id": latest.get("_id"),
                    "originalFilename": latest.get("command", {}).get("originalFilename", "hammer.xlsm"),
                    "createdAt": latest.get("createdAt"),
                    "status": latest.get("status"),
                    "user": latest.get("user", {}).get("email", "unknown"),
                }
                
                print(f"[OK] Found latest hammer: {result['originalFilename']} ({result['_id'][:12]}...)")
                print(f"     Uploaded by: {result['user']} at {result['createdAt']}")
                
                return result
                
        except httpx.HTTPStatusError as e:
            print(f"[ERROR] HTTP error fetching history: {e.response.status_code}")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to fetch hammer history: {e}")
            return None
    
    async def download_hammer(self, history_id: str, filename: str = "hammer.xlsm") -> Optional[bytes]:
        """
        Download the hammer file bytes from Graphite API.
        
        Args:
            history_id: The _id from the history API response
            filename: Original filename for logging
            
        Returns:
            File bytes or None if download failed
        """
        url = f"{self.BASE_URL}{self.DOWNLOAD_ENDPOINT}/{history_id}"
        
        headers = {}
        if self.auth_cookie:
            headers["Cookie"] = self.auth_cookie
        
        self.on_progress(f"Downloading {filename}...", 0.3)
        print(f"[API] GET {url}")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                file_bytes = response.content
                print(f"[OK] Downloaded {len(file_bytes)} bytes")
                
                return file_bytes
                
        except httpx.HTTPStatusError as e:
            print(f"[ERROR] HTTP error downloading: {e.response.status_code}")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to download hammer: {e}")
            return None
    
    async def download_and_index(
        self, 
        company_query: str,
        clear_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Complete pipeline: find company → get history → download → index.
        
        Args:
            company_query: Company name or alias (e.g., "western digital")
            clear_existing: If True, clear hammer-index before indexing
            
        Returns:
            Dict with success status, records_count, error if any
        """
        print("\n" + "=" * 60)
        print("[HAMMER DOWNLOAD] STARTING DIRECT API DOWNLOAD PIPELINE")
        print("=" * 60)
        print(f"[QUERY] Company query: '{company_query}'")
        
        # Step 1: Find company
        self.on_progress("Searching for company...", 0.05)
        company = self.find_company(company_query)
        
        if not company:
            return {
                "success": False,
                "error": f"Company not found: '{company_query}'",
                "available_companies": [c["company_name"] for c in self.companies],
            }
        
        # Handle both 'id' and 'company_id' field names (Pinecone data may use either)
        company_id = company.get("id") or company.get("company_id")
        company_name = company.get("company_name", "Unknown Company")
        
        if not company_id:
            print(f"[ERROR] Company record missing 'id' field: {company}")
            return {
                "success": False,
                "error": f"Company '{company_name}' found but missing ID field in registry. Please update the company registry in Pinecone.",
                "company_data": company,
            }
        
        print(f"[OK] Found company: {company_name} (ID: {company_id})")
        
        # Step 2: Get latest hammer history
        self.on_progress(f"Fetching latest hammer for {company_name}...", 0.1)
        history = await self.get_latest_hammer_id(company_id)
        
        if not history:
            return {
                "success": False,
                "error": f"No hammer history found for {company_name}",
                "company_id": company_id,
            }
        
        history_id = history["_id"]
        filename = history["originalFilename"]
        
        # Step 3: Download file
        self.on_progress(f"Downloading {filename}...", 0.25)
        file_bytes = await self.download_hammer(history_id, filename)
        
        if not file_bytes:
            return {
                "success": False,
                "error": f"Failed to download hammer file",
                "history_id": history_id,
            }
        
        print(f"[OK] Downloaded {len(file_bytes)} bytes")
        
        # Step 4: Index using HammerIndexer
        self.on_progress("Indexing to Pinecone...", 0.5)
        print("\n[INDEXER] Starting Pinecone indexing...")
        
        try:
            indexer = get_hammer_indexer(on_progress=self.on_progress)
            result = indexer.index_hammer_from_bytes(
                data=file_bytes,
                filename=filename,
                clear_existing=clear_existing
            )
            
            if result.get("success"):
                print(f"\n[SUCCESS] Hammer indexed successfully!")
                print(f"   Records: {result.get('records_count', 0)}")
                print(f"   Sheets: {result.get('sheets', [])}")
                
                return {
                    "success": True,
                    "company_name": company_name,
                    "company_id": company_id,
                    "filename": filename,
                    "records_count": result.get("records_count", 0),
                    "sheets": result.get("sheets", []),
                    "indexed_at": datetime.now().isoformat(),
                    "history_id": history_id,
                    "uploaded_by": history.get("user"),
                    "uploaded_at": history.get("createdAt"),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Indexing failed"),
                    "company_name": company_name,
                }
                
        except Exception as e:
            print(f"[ERROR] Indexing failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "company_name": company_name,
            }


# =============================================================================
# SINGLETON & HELPERS
# =============================================================================

_downloader: Optional[HammerDownloader] = None

def get_hammer_downloader(
    auth_cookie: Optional[str] = None,
    companies: List[Dict] = None,
    on_progress: Optional[Callable[[str, float], None]] = None
) -> HammerDownloader:
    """
    Get or create the HammerDownloader instance.
    
    Note: If auth_cookie is provided, it always creates a new instance
    to ensure fresh credentials are used.
    """
    global _downloader
    
    # Always create new instance when auth_cookie OR companies is provided
    # This ensures we use fresh browser session cookies and latest registry
    if auth_cookie or companies:
        print(f"[DOWNLOADER] Creating new instance (fresh cookies/companies)")
        _downloader = HammerDownloader(auth_cookie=auth_cookie, companies=companies, on_progress=on_progress)
        return _downloader
    
    # Reuse singleton only when nothing provided and it already exists
    if _downloader is None:
        print("[DOWNLOADER] Creating singleton instance (empty config)")
        _downloader = HammerDownloader(on_progress=on_progress)
        
    return _downloader


def parse_companies_from_text(text: str) -> List[Dict]:
    """
    Extract the COMPANIES list from a python-like text string (e.g., from Pinecone step).
    
    Args:
        text: The text content containing 'COMPANIES = [...]'
        
    Returns:
        List of company dicts
    """
    import ast
    
    try:
        # Find start of list
        start_marker = "COMPANIES = ["
        start_idx = text.find(start_marker)
        
        if start_idx == -1:
            print("[REGISTRY] Could not find 'COMPANIES = [' block in text")
            return []
            
        # Move index to opening bracket
        start_bracket_idx = start_idx + len("COMPANIES = ")
        
        # Find matching closing bracket
        balance = 0
        end_idx = -1
        
        for i, char in enumerate(text[start_bracket_idx:], start_bracket_idx):
            if char == '[':
                balance += 1
            elif char == ']':
                balance -= 1
                if balance == 0:
                    end_idx = i + 1  # Include the closing bracket
                    break
        
        if end_idx != -1:
            list_str = text[start_bracket_idx:end_idx]
            # Safe evaluation
            companies = ast.literal_eval(list_str)
            if isinstance(companies, list):
                print(f"[REGISTRY] Successfully parsed {len(companies)} companies from text")
                return companies
                
        print("[REGISTRY] Could not find matching closing bracket for COMPANIES list")
        return []
        
    except Exception as e:
        print(f"[REGISTRY] Failed to parse companies: {e}")
        return []


def is_hammer_download_intent(goal: str) -> bool:
    """
    Detect if the user's goal is to download a hammer file.
    
    This is used by the goal_decomposer to route directly to
    the HammerDownloader instead of using browser automation.
    
    Args:
        goal: User's natural language goal
        
    Returns:
        True if this looks like a hammer download request
    """
    goal_lower = goal.lower()
    
    # English patterns (including gerund forms for decomposed subtasks)
    en_patterns = [
        "download hammer",
        "downloading hammer",
        "get hammer",
        "getting hammer",
        "fetch hammer",
        "fetching hammer",
        "download the hammer",
        "get the hammer",
        "download hammer file",
        "get hammer file",
        "hammer via api",
        "hammer from western",
        "hammer from adobe",
        "hammer from vonage",
        "hammer from air",
        "western digital hammer",
        "adobe hammer",
        "vonage hammer",
    ]
    
    # Spanish patterns
    es_patterns = [
        "descargar hammer",
        "descargando hammer",
        "descarga hammer",
        "descargar el hammer",
        "descarga el hammer",
        "obtener hammer",
        "obteniendo hammer",
        "bajar hammer",
        "bajando hammer",
        "hammer de western",
        "hammer de adobe",
    ]
    
    all_patterns = en_patterns + es_patterns
    
    all_patterns = en_patterns + es_patterns
    
    for pattern in all_patterns:
        if pattern in goal_lower:
            return True
            
    # Add fuzzy/typo checks
    import re
    # Matches "download hamme", "get hamme", "hamme for"
    if re.search(r"(?:download|get|fetch|descargar|bajar).{1,10}hamm?e", goal_lower):
        return True
    
    # Matches "hamme for/from/de" 
    if re.search(r"hamm?e\s+(?:for|from|de|para)", goal_lower):
        return True
    
    return False


def extract_company_from_goal(goal: str) -> Optional[str]:
    """
    Extract company name from a goal like "download hammer from Western Digital".
    
    Handles typos like 'fron' instead of 'from', and various phrasing patterns.
    
    Returns the company portion or None if not parseable.
    """
    import re
    
    # Patterns to extract company name
    # Note: Added 'fron|frm' for common typos of 'from'
    patterns = [
        # "download hammer from/fron/de company" (supports hamme/hammer)
        r"(?:download|downloading|get|getting|fetch|fetching|descargar|descargando|descarga|obtener|bajar)\s+(?:the\s+)?hamm?e(?:r)?\s+(?:file\s+)?(?:from|fron|frm|de|para)\s+(.+)",
        # "download company hammer" or "download company's hammer"
        r"(?:download|downloading|get|getting|fetch|fetching|descargar)\s+(?:the\s+)?(.+?)(?:'s)?\s+hamm?e(?:r)?",
        # "hammer from company"
        r"hamm?e(?:r)?\s+(?:from|fron|frm|de|para)\s+(.+)",
        # "hammer via api" patterns - fallback to check for company name in goal
        r"hamm?e(?:r)?.+?(?:western|adobe|vonage|air|linde)",
    ]
    
    for pattern in patterns[:-1]:  # Skip the last fallback pattern initially
        match = re.search(pattern, goal, re.IGNORECASE)
        if match:
            company = match.group(1).strip()
            # Clean up common suffixes/noise
            company = re.sub(r"\s*(?:please|por favor|now|ahora|via\s+api)?\.?$", "", company, flags=re.IGNORECASE)
            # Remove "the" prefix if present
            company = re.sub(r"^the\s+", "", company, flags=re.IGNORECASE)
            
            # Skip if we extracted something clearly wrong (like "the")
            if company.lower() in ["the", "a", "an", ""]:
                continue
                
            return company
    
    # Fallback: look for known company names directly
    known_companies = ["western", "adobe", "vonage", "air liquide", "linde"]
    goal_lower = goal.lower()
    for company in known_companies:
        if company in goal_lower:
            return company
    
    return None


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        if len(sys.argv) < 2:
            print("Usage: python hammer_downloader.py <company_name>")
            print("\nAvailable companies:")
            for c in COMPANIES:
                print(f"  - {c['company_name']} ({c['id']})")
            return
        
        company_query = " ".join(sys.argv[1:])
        
        def progress(msg: str, pct: float):
            print(f"[{pct*100:.0f}%] {msg}")
        
        # Since we removed the hardcoded list, we need to provide one for testing
        test_companies = [
            {
                "company_name": "Western Digital Technologies, Inc.",
                "id": "US66254",
                "aliases": ["western", "western digital", "wd", "wdc"]
            }
        ]
        
        downloader = HammerDownloader(companies=test_companies, on_progress=progress)
        result = await downloader.download_and_index(company_query)
        
        print("\n" + "=" * 60)
        print("[RESULT]")
        print(json.dumps(result, indent=2, default=str))
    
    asyncio.run(main())
