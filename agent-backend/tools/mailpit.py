"""Mailpit API Client - Email handling for 2FA and activation flows.

This module provides programmatic access to Mailpit's API for retrieving
activation emails, 2FA codes, and other email-based interactions. This is
much faster and more reliable than navigating Mailpit visually.

Mailpit API documentation: https://mailpit.axllent.org/docs/api-v1/
"""

import re
import os
import aiohttp
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EmailMessage:
    """Parsed email message from Mailpit."""
    id: str
    subject: str
    from_address: str
    to_addresses: List[str]
    date: datetime
    text_body: str
    html_body: str
    attachments: List[str]


class MailpitClient:
    """
    Async client for Mailpit API.
    
    Provides methods to:
    - Fetch emails by recipient or subject
    - Extract activation links and 2FA codes
    - Search for specific patterns in email bodies
    
    Default configuration uses environment variables or localhost:8025.
    """
    
    def __init__(
        self, 
        host: Optional[str] = None, 
        port: Optional[int] = None
    ):
        """
        Initialize Mailpit client.
        
        Args:
            host: Mailpit host (default: from MAILPIT_HOST env or localhost)
            port: Mailpit API port (default: from MAILPIT_PORT env or 8025)
        """
        self.host = host or os.getenv("MAILPIT_HOST", "localhost")
        self.port = port or int(os.getenv("MAILPIT_PORT", "8025"))
        self.base_url = f"http://{self.host}:{self.port}/api/v1"
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make async HTTP request to Mailpit API."""
        url = f"{self.base_url}{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return {}
                else:
                    raise Exception(f"Mailpit API error: {response.status}")
    
    async def get_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get list of messages from Mailpit.
        
        Args:
            limit: Maximum number of messages to return
        
        Returns:
            List of message summaries
        """
        try:
            result = await self._request("GET", f"/messages?limit={limit}")
            return result.get("messages", [])
        except Exception as e:
            print(f"⚠️ Mailpit: Could not fetch messages: {e}")
            return []
    
    async def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full message details by ID.
        
        Args:
            message_id: The message ID from Mailpit
        
        Returns:
            Full message data or None if not found
        """
        try:
            return await self._request("GET", f"/message/{message_id}")
        except Exception as e:
            print(f"⚠️ Mailpit: Could not fetch message {message_id}: {e}")
            return None
    
    async def get_latest_email(
        self, 
        recipient: Optional[str] = None,
        subject_contains: Optional[str] = None
    ) -> Optional[EmailMessage]:
        """
        Get the most recent email, optionally filtered.
        
        Args:
            recipient: Filter by recipient email address
            subject_contains: Filter by subject containing this string
        
        Returns:
            EmailMessage or None if no matching email found
        """
        messages = await self.get_messages(limit=100)
        
        for msg_summary in messages:
            # Check recipient filter
            if recipient:
                to_addresses = [addr.get("Address", "") for addr in msg_summary.get("To", [])]
                if not any(recipient.lower() in addr.lower() for addr in to_addresses):
                    continue
            
            # Check subject filter
            if subject_contains:
                subject = msg_summary.get("Subject", "")
                if subject_contains.lower() not in subject.lower():
                    continue
            
            # Found a match, get full message
            msg_id = msg_summary.get("ID")
            full_msg = await self.get_message(msg_id)
            
            if full_msg:
                return self._parse_message(full_msg)
        
        return None
    
    def _parse_message(self, raw: Dict[str, Any]) -> EmailMessage:
        """Parse raw Mailpit message into EmailMessage dataclass."""
        return EmailMessage(
            id=raw.get("ID", ""),
            subject=raw.get("Subject", ""),
            from_address=raw.get("From", {}).get("Address", ""),
            to_addresses=[addr.get("Address", "") for addr in raw.get("To", [])],
            date=datetime.fromisoformat(raw.get("Date", "2000-01-01T00:00:00").replace("Z", "+00:00")),
            text_body=raw.get("Text", ""),
            html_body=raw.get("HTML", ""),
            attachments=[att.get("FileName", "") for att in raw.get("Attachments", [])]
        )
    
    async def check_email_for_token(
        self, 
        subject: str, 
        recipient: Optional[str] = None,
        pattern: Optional[str] = None
    ) -> Optional[str]:
        """
        Search for activation token or code in email body.
        
        Args:
            subject: Subject to search for (partial match)
            recipient: Optional recipient email filter
            pattern: Optional regex pattern for extraction (default: common patterns)
        
        Returns:
            Extracted token/code or None if not found
        """
        email = await self.get_latest_email(
            recipient=recipient,
            subject_contains=subject
        )
        
        if not email:
            print(f"📭 Mailpit: No email found with subject '{subject}'")
            return None
        
        # Common token patterns
        patterns = [
            r'(?:code|token|otp|verification)[:\s]*([A-Z0-9]{4,8})',  # Codes
            r'\b(\d{6})\b',  # 6-digit codes
            r'\b(\d{4})\b',  # 4-digit codes
        ]
        
        if pattern:
            patterns.insert(0, pattern)
        
        # Search in both text and HTML body
        search_text = f"{email.text_body} {email.html_body}"
        
        for pat in patterns:
            match = re.search(pat, search_text, re.IGNORECASE)
            if match:
                token = match.group(1)
                print(f"🔑 Mailpit: Found token: {token}")
                return token
        
        print(f"🔍 Mailpit: No token found in email '{email.subject}'")
        return None
    
    async def extract_activation_link(
        self, 
        subject: str,
        recipient: Optional[str] = None,
        link_pattern: Optional[str] = None
    ) -> Optional[str]:
        """
        Extract activation or verification link from email.
        
        Args:
            subject: Subject to search for (partial match)
            recipient: Optional recipient email filter
            link_pattern: Optional regex for specific link pattern
        
        Returns:
            Extracted URL or None if not found
        """
        email = await self.get_latest_email(
            recipient=recipient,
            subject_contains=subject
        )
        
        if not email:
            print(f"📭 Mailpit: No email found with subject '{subject}'")
            return None
        
        # Common link patterns for activation emails
        patterns = [
            r'href=["\']([^"\']*(?:activate|verify|confirm|reset|token)[^"\']*)["\']',  # HTML links
            r'(https?://[^\s<>"\']+(?:activate|verify|confirm|reset|token)[^\s<>"\']*)',  # Plain URLs
            r'(https?://[^\s<>"\']+)',  # Any URL (fallback)
        ]
        
        if link_pattern:
            patterns.insert(0, link_pattern)
        
        # Search in HTML body first (more reliable), then text
        search_sources = [email.html_body, email.text_body]
        
        for source in search_sources:
            for pat in patterns[:-1]:  # Skip generic URL pattern initially
                match = re.search(pat, source, re.IGNORECASE)
                if match:
                    url = match.group(1)
                    # Clean up HTML entities
                    url = url.replace("&amp;", "&")
                    print(f"🔗 Mailpit: Found activation link: {url[:80]}...")
                    return url
        
        # Last resort: any URL
        for source in search_sources:
            match = re.search(patterns[-1], source)
            if match:
                url = match.group(1)
                print(f"🔗 Mailpit: Found URL (generic): {url[:80]}...")
                return url
        
        print(f"🔍 Mailpit: No link found in email '{email.subject}'")
        return None
    
    async def wait_for_email(
        self, 
        subject_contains: str,
        recipient: Optional[str] = None,
        timeout_seconds: int = 30,
        poll_interval: float = 2.0
    ) -> Optional[EmailMessage]:
        """
        Wait for an email to arrive.
        
        Args:
            subject_contains: Subject string to wait for
            recipient: Optional recipient filter
            timeout_seconds: Maximum wait time
            poll_interval: Seconds between checks
        
        Returns:
            EmailMessage when found, or None on timeout
        """
        import asyncio
        
        elapsed = 0.0
        while elapsed < timeout_seconds:
            email = await self.get_latest_email(
                recipient=recipient,
                subject_contains=subject_contains
            )
            
            if email:
                print(f"📬 Mailpit: Email arrived: '{email.subject}'")
                return email
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        print(f"⏰ Mailpit: Timeout waiting for email with subject '{subject_contains}'")
        return None
    
    async def delete_all_messages(self) -> bool:
        """
        Delete all messages from Mailpit (useful for test cleanup).
        
        Returns:
            True if successful
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(f"{self.base_url}/messages") as response:
                    if response.status in [200, 204]:
                        print("🗑️ Mailpit: All messages deleted")
                        return True
            return False
        except Exception as e:
            print(f"⚠️ Mailpit: Could not delete messages: {e}")
            return False


# Singleton instance
_client: Optional[MailpitClient] = None


def get_mailpit_client() -> MailpitClient:
    """Get the singleton MailpitClient instance."""
    global _client
    if _client is None:
        _client = MailpitClient()
    return _client
