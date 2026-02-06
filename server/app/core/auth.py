"""Auth0 JWT verification and authentication dependencies."""
import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, jwk
from jose.utils import base64url_decode
import requests
from functools import lru_cache
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import User


# HTTPBearer scheme for extracting JWT from Authorization header
security = HTTPBearer()


class Auth0JWTVerifier:
    """Verifies Auth0 JWT tokens using JWKS."""
    
    def __init__(self):
        self.jwks_url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
        self._jwks_cache = None
    
    @lru_cache(maxsize=1)
    def get_jwks(self) -> dict:
        """Fetch and cache Auth0 JWKS (JSON Web Key Set)."""
        if self._jwks_cache is None:
            response = requests.get(self.jwks_url, timeout=10)
            response.raise_for_status()
            self._jwks_cache = response.json()
        return self._jwks_cache
    
    def verify_token(self, token: str) -> dict:
        """
        Verify JWT token and return decoded payload.
        
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            # Get the key ID from token header
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            if not kid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: Missing key ID",
                )
            
            # Find the matching public key
            jwks = self.get_jwks()
            rsa_key = None
            
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"],
                    }
                    break
            
            if not rsa_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: Unable to find appropriate key",
                )
            
            # Verify and decode the token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=settings.AUTH0_ALGORITHMS,
                audience=settings.AUTH0_API_AUDIENCE,
                issuer=settings.AUTH0_ISSUER,
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.JWTClaimsError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims",
            )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token verification failed: {str(e)}",
            )


# Global verifier instance
verifier = Auth0JWTVerifier()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Dependency to verify JWT token and return Auth0 user ID (sub claim).
    
    Returns:
        str: Auth0 user ID (e.g., "auth0|123456")
    """
    token = credentials.credentials
    payload = verifier.verify_token(token)
    
    # Extract user ID from 'sub' claim
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: Missing subject claim",
        )
    
    return user_id


async def get_current_user(
    user_id: str = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency to get or create the current authenticated user.
    
    If user doesn't exist in database, creates a new user record.
    
    Returns:
        User: The authenticated user model
    """
    from sqlalchemy import select
    
    # Check if user exists
    result = await db.execute(
        select(User).where(User.auth0_user_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Create new user (you might want to get email from token claims)
        # For now, we'll create a minimal user record
        # In production, you'd fetch user info from Auth0 Management API or token claims
        user = User(
            auth0_user_id=user_id,
            email=f"{user_id}@placeholder.com",  # Replace with actual email from token
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Optional authentication dependency.
    Returns user if authenticated, None otherwise.
    Use for endpoints that have different behavior for authenticated vs anonymous users.
    """
    if not credentials:
        return None
    
    try:
        user_id = await verify_token(credentials)
        return await get_current_user(user_id, db)
    except HTTPException:
        return None
