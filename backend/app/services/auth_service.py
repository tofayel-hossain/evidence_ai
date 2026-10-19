import os
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt

from backend.app.config import settings

class AuthService:
    """
    Handles secure PBKDF2-HMAC-SHA256 password hashing and JWT token lifecycle.
    """

    @staticmethod
    def hash_password(password: str) -> str:
        """Hashes password using PBKDF2-HMAC-SHA256 with a unique cryptographic salt."""
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return salt.hex() + ":" + key.hex()

    @staticmethod
    def verify_password(plain_password: str, stored_hash: str) -> bool:
        """Verifies a plain password against stored salt:key string using constant-time compare."""
        try:
            parts = stored_hash.split(":")
            if len(parts) != 2:
                return False
            salt = bytes.fromhex(parts[0])
            original_key = bytes.fromhex(parts[1])
            new_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100000)
            return hmac.compare_digest(original_key, new_key)
        except Exception:
            return False

    @staticmethod
    def create_access_token(user_id: str, email: str, expires_delta: Optional[timedelta] = None) -> str:
        """Encodes user identity into a signed JWT bearer token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode = {
            "sub": user_id,
            "email": email,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
        """Decodes and validates JWT token signature and expiration."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except (jwt.PyJWTError, Exception):
            return None
