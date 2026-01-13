"""
Session Service - Manages user sessions and company metadata.

Provides:
- User namespace generation for Pinecone isolation
- Company metadata storage/retrieval from Pinecone
- Session context tracking
"""
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class CompanyMetadata:
    """Metadata about the indexed hammer's company."""
    company_id: str
    company_name: str
    indexed_at: str
    hammer_filename: str
    jira_label: Optional[str] = None
    record_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompanyMetadata":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SessionService:
    """
    Manages user sessions and company metadata for multi-tenant isolation.
    
    Each user gets a dedicated Pinecone namespace: user_{user_id}
    Company metadata is stored in a special namespace for quick retrieval.
    """
    
    # Namespace for storing company metadata (separate from hammer vectors)
    METADATA_NAMESPACE = "company_metadata"
    METADATA_ID_PREFIX = "meta_"
    
    def __init__(self, pinecone_service=None):
        """
        Initialize session service.
        
        Args:
            pinecone_service: Optional PineconeService for metadata storage
        """
        self._pinecone = pinecone_service
        self._cache: Dict[str, CompanyMetadata] = {}
        
    @property
    def pinecone(self):
        """Lazy load PineconeService to avoid circular imports."""
        if self._pinecone is None:
            from pinecone_service import PineconeService
            self._pinecone = PineconeService()
        return self._pinecone
    
    def get_user_namespace(self, user_id: str) -> str:
        """
        Generate namespace for a user's hammer vectors.
        
        Args:
            user_id: User identifier (email or sub from JWT)
            
        Returns:
            Namespace string: user_{user_id_hash}
        """
        # Create a clean, safe namespace from user_id
        # Replace special chars and limit length for Pinecone
        import hashlib
        
        # Use hash to handle emails/special chars safely
        user_hash = hashlib.md5(user_id.encode()).hexdigest()[:12]
        return f"user_{user_hash}"
    
    def store_company_metadata(
        self,
        user_id: str,
        company_id: str,
        company_name: str,
        hammer_filename: str,
        record_count: int = 0,
        jira_label: Optional[str] = None
    ) -> CompanyMetadata:
        """
        Store company metadata for a user's indexed hammer.
        
        This is stored in-memory and optionally in Pinecone for persistence.
        
        Args:
            user_id: User identifier
            company_id: Company ID from hammer (e.g., "US66254")
            company_name: Company name (e.g., "Western Digital")
            hammer_filename: Original filename
            record_count: Number of vectors indexed
            jira_label: Optional matching Jira label
            
        Returns:
            CompanyMetadata object
        """
        metadata = CompanyMetadata(
            company_id=company_id,
            company_name=company_name,
            indexed_at=datetime.now().isoformat(),
            hammer_filename=hammer_filename,
            jira_label=jira_label,
            record_count=record_count
        )
        
        # Cache in memory
        namespace = self.get_user_namespace(user_id)
        self._cache[namespace] = metadata
        
        print(f"[SESSION] Stored company metadata for {user_id}: {company_name} ({company_id})")
        
        return metadata
    
    def get_company_metadata(self, user_id: str) -> Optional[CompanyMetadata]:
        """
        Get company metadata for a user's current session.
        
        Args:
            user_id: User identifier
            
        Returns:
            CompanyMetadata if exists, None otherwise
        """
        namespace = self.get_user_namespace(user_id)
        
        # Check cache first
        if namespace in self._cache:
            return self._cache[namespace]
        
        return None
    
    def clear_user_session(self, user_id: str) -> bool:
        """
        Clear a user's session data (metadata cache only, not vectors).
        
        Args:
            user_id: User identifier
            
        Returns:
            True if cleared, False if not found
        """
        namespace = self.get_user_namespace(user_id)
        
        if namespace in self._cache:
            del self._cache[namespace]
            print(f"[SESSION] Cleared session for {user_id}")
            return True
        
        return False
    
    def get_all_active_sessions(self) -> Dict[str, CompanyMetadata]:
        """
        Get all active sessions (for debugging/monitoring).
        
        Returns:
            Dict of namespace -> CompanyMetadata
        """
        return self._cache.copy()


# Singleton instance
_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    """Get the singleton SessionService instance."""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
