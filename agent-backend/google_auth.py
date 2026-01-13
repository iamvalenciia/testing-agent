"""Google OAuth Authentication Service for Enterprise Login.

This service handles:
1. Google ID Token verification via Google's auth library
2. Domain validation (only @graphiteconnect.com allowed)
3. Internal JWT session token creation/verification
4. FastAPI dependency for protecting routes
"""
import os
import time
from typing import Optional, Dict
from datetime import datetime, timedelta

import jwt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi import HTTPException, Depends, Header, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import config

# Security scheme for FastAPI docs
security = HTTPBearer(auto_error=False)


class GoogleAuthService:
    """Handles Google OAuth and session management."""
    
    def __init__(self):
        self.client_id = config.GOOGLE_CLIENT_ID
        self.allowed_domain = config.ALLOWED_EMAIL_DOMAIN
        self.secret_key = config.SESSION_SECRET_KEY
        self.expiry_days = config.SESSION_EXPIRY_DAYS
        
    def verify_google_token(self, token: str) -> Dict:
        """
        Verify Google ID token and extract user info.
        
        Args:
            token: The Google ID token from frontend
            
        Returns:
            Dict with user info: {email, name, picture, hd}
            
        Raises:
            HTTPException: If token is invalid or domain unauthorized
        """
        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                token, 
                google_requests.Request(), 
                self.client_id
            )
            
            # Verify issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token issuer"
                )
            
            # Extract user info
            email = idinfo.get('email', '')
            name = idinfo.get('name', '')
            picture = idinfo.get('picture', '')
            hd = idinfo.get('hd', '')  # Hosted domain for Google Workspace
            
            # Validate email domain
            email_domain = email.split('@')[-1] if '@' in email else ''
            
            if email_domain != self.allowed_domain and hd != self.allowed_domain:
                print(f"[AUTH] Rejected login attempt from: {email} (domain: {email_domain})")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access restricted to authorized employees only"
                )
            
            print(f"[AUTH] Verified Google token for: {email}")
            
            return {
                'email': email,
                'name': name,
                'picture': picture,
                'hd': hd,
                'sub': idinfo.get('sub', ''),  # Google user ID
            }
            
        except ValueError as e:
            print(f"[AUTH] Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        except HTTPException:
            raise
        except Exception as e:
            print(f"[AUTH] Unexpected error during verification: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error"
            )
    
    def create_session_token(self, user_info: Dict) -> str:
        """
        Create internal JWT session token.
        
        Args:
            user_info: User info from Google verification
            
        Returns:
            JWT token string
        """
        payload = {
            'sub': user_info['sub'],
            'email': user_info['email'],
            'name': user_info['name'],
            'picture': user_info['picture'],
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(days=self.expiry_days),
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        print(f"[AUTH] Created session token for: {user_info['email']} (expires in {self.expiry_days} days)")
        
        return token
    
    def verify_session_token(self, token: str) -> Dict:
        """
        Verify internal session token.
        
        Args:
            token: JWT session token
            
        Returns:
            Dict with user info from token payload
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return {
                'sub': payload['sub'],
                'email': payload['email'],
                'name': payload['name'],
                'picture': payload['picture'],
            }
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please login again."
            )
        except jwt.InvalidTokenError as e:
            print(f"[AUTH] Invalid session token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session token"
            )


# Singleton instance
_google_auth_service: Optional[GoogleAuthService] = None


def get_google_auth_service() -> GoogleAuthService:
    """Get or create singleton GoogleAuthService instance."""
    global _google_auth_service
    if _google_auth_service is None:
        _google_auth_service = GoogleAuthService()
    return _google_auth_service


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(None),
) -> Dict:
    """
    FastAPI dependency to get current authenticated user.
    
    Can receive token via:
    1. Authorization: Bearer <token> header
    2. authorization header directly
    
    Returns:
        User info dict
        
    Raises:
        HTTPException: If not authenticated
    """
    token = None
    
    # Try Bearer token first
    if credentials and credentials.credentials:
        token = credentials.credentials
    # Fallback to direct header
    elif authorization:
        if authorization.startswith('Bearer '):
            token = authorization[7:]
        else:
            token = authorization
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    auth_service = get_google_auth_service()
    return auth_service.verify_session_token(token)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(None),
) -> Optional[Dict]:
    """
    Optional authentication - returns None if not authenticated.
    Useful for endpoints that work differently based on auth state.
    """
    try:
        return await get_current_user(credentials, authorization)
    except HTTPException:
        return None


def get_websocket_token(token: Optional[str] = Query(None)) -> Optional[str]:
    """Extract token from WebSocket query parameters."""
    return token
