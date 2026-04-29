"""Authentication service with token persistence."""
import json
import os
from datetime import datetime
from pathlib import Path

import jwt

from config import config


class AuthService:
    """Handles authentication token management with persistence."""
    
    def __init__(self):
        self.token: str | None = None
        self.refresh_token: str | None = None
        self.user_info: dict | None = None
        self._token_file = Path(__file__).parent.parent / config.AUTH_TOKEN_FILE
        self._load_tokens()
    
    def _load_tokens(self) -> None:
        """Load tokens from file on startup."""
        try:
            if self._token_file.exists():
                with open(self._token_file, "r") as f:
                    data = json.load(f)
                    self.token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    
                    # Validate token is not expired
                    if self.token and self._is_token_expired(self.token):
                        self.clear_tokens()
                    else:
                        self._decode_user_info()
        except Exception as e:
            print(f"Error loading tokens: {e}")
            self.clear_tokens()
    
    def _save_tokens(self) -> None:
        """Persist tokens to file."""
        try:
            data = {
                "access_token": self.token,
                "refresh_token": self.refresh_token,
                "saved_at": datetime.utcnow().isoformat(),
            }
            with open(self._token_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving tokens: {e}")
    
    def _is_token_expired(self, token: str) -> bool:
        """Check if JWT token is expired."""
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get("exp")
            if exp:
                return datetime.utcnow().timestamp() > exp
            return False
        except Exception:
            return True
    
    def _decode_user_info(self) -> None:
        """Decode user info from JWT."""
        if not self.token:
            self.user_info = None
            return
        try:
            payload = jwt.decode(self.token, options={"verify_signature": False})
            self.user_info = {
                "user_id": payload.get("sub"),
                "email": payload.get("email"),
                "role": payload.get("role"),
                "tenant_id": payload.get("tenant_id"),
            }
        except Exception as e:
            print(f"Error decoding token: {e}")
            self.user_info = None
    
    def set_tokens(self, access_token: str, refresh_token: str | None = None) -> None:
        """Set tokens and persist."""
        self.token = access_token
        self.refresh_token = refresh_token
        self._decode_user_info()
        self._save_tokens()
    
    def clear_tokens(self) -> None:
        """Clear all tokens."""
        self.token = None
        self.refresh_token = None
        self.user_info = None
        try:
            if self._token_file.exists():
                os.remove(self._token_file)
        except Exception as e:
            print(f"Error clearing tokens: {e}")
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated with valid token."""
        if not self.token:
            return False
        return not self._is_token_expired(self.token)
    
    def is_super_admin(self) -> bool:
        """Check if current user is SUPER_ADMIN."""
        if not self.user_info:
            return False
        return self.user_info.get("role") == "SUPER_ADMIN"
    
    def get_headers(self) -> dict:
        """Get authorization headers."""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}


# Global auth service instance
auth_service = AuthService()
