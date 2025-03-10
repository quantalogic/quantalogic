import json
from typing import Any, Dict, Optional
from functools import wraps

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from hkdf import Hkdf
from jose.jwe import decrypt
from loguru import logger
import os

security = HTTPBearer()

def __encryption_key(secret: str) -> bytes:
    """Generate the encryption key using HKDF."""
    return Hkdf("", bytes(secret, "utf-8")).expand(b"NextAuth.js Generated Encryption Key", 32)

def decode_jwe(token: str, secret: str) -> Optional[Dict[str, Any]]:
    """Decrypt and decode a JWE token."""
    try:
        decrypted = decrypt(token, __encryption_key(secret))
        if decrypted:
            return json.loads(bytes.decode(decrypted, "utf-8"))
        return None
    except Exception as e:
        logger.error(f"Error decoding JWE token: {str(e)}")
        return None

def require_auth(func):
    """FastAPI compatible authentication decorator."""
    async def wrapper(*args, credentials: HTTPAuthorizationCredentials = Security(security), **kwargs):
        jwt_secret = os.getenv("JWT_SECRET")
        
        if not jwt_secret:
            logger.error("JWT_SECRET not configured")
            raise HTTPException(
                status_code=500,
                detail="Server configuration error"
            )
        
        token = credentials.credentials
        payload = decode_jwe(token, jwt_secret)
        
        if not payload:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
            
        # Add user info to kwargs
        kwargs['user'] = payload
        return await func(*args, **kwargs)
    
    return wrapper