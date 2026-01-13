"""Tests for Google OAuth authentication service."""
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta
import jwt


class TestGoogleAuthService:
    """Tests for GoogleAuthService class."""
    
    def test_create_session_token(self):
        """Test JWT session token creation."""
        import config
        config.GOOGLE_CLIENT_ID = 'test-client-id'
        config.SESSION_SECRET_KEY = 'test-secret-key'
        config.SESSION_EXPIRY_DAYS = 30
        config.ALLOWED_EMAIL_DOMAIN = 'graphiteconnect.com'
        
        from google_auth import GoogleAuthService
        
        service = GoogleAuthService()
        
        user_info = {
            'sub': '12345',
            'email': 'test@graphiteconnect.com',
            'name': 'Test User',
            'picture': 'https://example.com/avatar.jpg',
        }
        
        token = service.create_session_token(user_info)
        
        # Verify token is valid JWT
        assert token is not None
        assert isinstance(token, str)
        
        # Decode and verify payload
        payload = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
        assert payload['sub'] == '12345'
        assert payload['email'] == 'test@graphiteconnect.com'
        assert payload['name'] == 'Test User'
        assert 'exp' in payload
    
    def test_verify_session_token_valid(self):
        """Test session token verification with valid token."""
        import config
        config.GOOGLE_CLIENT_ID = 'test-client-id'
        config.SESSION_SECRET_KEY = 'test-secret-key'
        config.SESSION_EXPIRY_DAYS = 30
        config.ALLOWED_EMAIL_DOMAIN = 'graphiteconnect.com'
        
        from google_auth import GoogleAuthService
        
        service = GoogleAuthService()
        
        user_info = {
            'sub': '12345',
            'email': 'test@graphiteconnect.com',
            'name': 'Test User',
            'picture': 'https://example.com/avatar.jpg',
        }
        token = service.create_session_token(user_info)
        
        result = service.verify_session_token(token)
        
        assert result['sub'] == '12345'
        assert result['email'] == 'test@graphiteconnect.com'
    
    def test_verify_session_token_expired(self):
        """Test session token verification with expired token."""
        import config
        config.GOOGLE_CLIENT_ID = 'test-client-id'
        config.SESSION_SECRET_KEY = 'test-secret-key'
        config.SESSION_EXPIRY_DAYS = 30
        config.ALLOWED_EMAIL_DOMAIN = 'graphiteconnect.com'
        
        from google_auth import GoogleAuthService
        from fastapi import HTTPException
        
        service = GoogleAuthService()
        
        expired_payload = {
            'sub': '12345',
            'email': 'test@graphiteconnect.com',
            'name': 'Test User',
            'picture': 'https://example.com/avatar.jpg',
            'iat': datetime.utcnow() - timedelta(days=60),
            'exp': datetime.utcnow() - timedelta(days=30),
        }
        expired_token = jwt.encode(expired_payload, 'test-secret-key', algorithm='HS256')
        
        with pytest.raises(HTTPException) as exc_info:
            service.verify_session_token(expired_token)
        
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @patch('google_auth.id_token.verify_oauth2_token')
    def test_reject_unauthorized_domain(self, mock_verify):
        """Test that non-graphiteconnect.com emails are rejected."""
        import config
        config.GOOGLE_CLIENT_ID = 'test-client-id'
        config.SESSION_SECRET_KEY = 'test-secret-key'
        config.SESSION_EXPIRY_DAYS = 30
        config.ALLOWED_EMAIL_DOMAIN = 'graphiteconnect.com'
        
        from google_auth import GoogleAuthService
        from fastapi import HTTPException
        
        service = GoogleAuthService()
        
        mock_verify.return_value = {
            'iss': 'accounts.google.com',
            'email': 'user@gmail.com',
            'name': 'Outside User',
            'picture': 'https://example.com/avatar.jpg',
            'hd': '',
            'sub': '99999',
        }
        
        with pytest.raises(HTTPException) as exc_info:
            service.verify_google_token('fake-token')
        
        assert exc_info.value.status_code == 403
        assert "authorized employees" in exc_info.value.detail.lower()
    
    @patch('google_auth.id_token.verify_oauth2_token')
    def test_accept_authorized_domain(self, mock_verify):
        """Test that graphiteconnect.com emails are accepted."""
        import config
        config.GOOGLE_CLIENT_ID = 'test-client-id'
        config.SESSION_SECRET_KEY = 'test-secret-key'
        config.SESSION_EXPIRY_DAYS = 30
        config.ALLOWED_EMAIL_DOMAIN = 'graphiteconnect.com'
        
        from google_auth import GoogleAuthService
        
        service = GoogleAuthService()
        
        mock_verify.return_value = {
            'iss': 'accounts.google.com',
            'email': 'employee@graphiteconnect.com',
            'name': 'Authorized Employee',
            'picture': 'https://example.com/avatar.jpg',
            'hd': 'graphiteconnect.com',
            'sub': '12345',
        }
        
        result = service.verify_google_token('fake-token')
        
        assert result['email'] == 'employee@graphiteconnect.com'
        assert result['name'] == 'Authorized Employee'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
