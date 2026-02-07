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
        if not settings.AUTH0_DOMAIN:
            raise ValueError("AUTH0_DOMAIN environment variable is not set")
        
        # Validate that AUTH0_DOMAIN looks like an Auth0 tenant domain or custom domain
        if not (".auth0.com" in settings.AUTH0_DOMAIN or ".auth0.app" in settings.AUTH0_DOMAIN):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"AUTH0_DOMAIN '{settings.AUTH0_DOMAIN}' is not an Auth0 tenant domain. "
                f"If this is a custom domain, ensure it is fully configured in Auth0 "
                f"and that https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json is reachable."
            )
        
        self.jwks_url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
        self._jwks_cache = None
    
    def get_jwks(self) -> dict:
        """Fetch and cache Auth0 JWKS (JSON Web Key Set)."""
        if self._jwks_cache is None:
            try:
                response = requests.get(self.jwks_url, timeout=5)
                response.raise_for_status()
                self._jwks_cache = response.json()
            except requests.exceptions.Timeout:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Timeout fetching Auth0 JWKS from {self.jwks_url}. Please check AUTH0_DOMAIN configuration."
                )
            except requests.exceptions.RequestException as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Failed to fetch Auth0 JWKS: {str(e)}. Please verify AUTH0_DOMAIN is correctly set to your Auth0 tenant domain (e.g., 'your-tenant.us.auth0.com')."
                )
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


async def upsert_user_from_token(
    db: AsyncSession, user_id: str, payload: dict
) -> User:
    """
    Ensure a users row exists for the authenticated subject.
    Inserts if missing, updates email/name/picture/updated_at if present.
    Handles nullable email safely.
    """
    from sqlalchemy import select
    from datetime import datetime
    import logging
    
    logger = logging.getLogger(__name__)

    # Try multiple possible claim locations for email, name, picture
    # Standard claims, custom namespaced claims, or Auth0-specific claims
    email = (
        payload.get("email") or 
        payload.get(f"https://{settings.AUTH0_DOMAIN}/email") or
        payload.get("https://tickerstats.com/email") or
        payload.get("http://tickerstats.com/email")
    )
    name = (
        payload.get("name") or 
        payload.get(f"https://{settings.AUTH0_DOMAIN}/name") or
        payload.get("https://tickerstats.com/name") or
        payload.get("http://tickerstats.com/name") or
        payload.get("nickname")
    )
    picture = (
        payload.get("picture") or 
        payload.get(f"https://{settings.AUTH0_DOMAIN}/picture") or
        payload.get("https://tickerstats.com/picture") or
        payload.get("http://tickerstats.com/picture")
    )
    
    # Log what we found for debugging
    if not email or not name:
        logger.warning(
            f"Missing user info from token for {user_id}: "
            f"email={'✓' if email else '✗'}, name={'✓' if name else '✗'}. "
            f"Available claims: {list(payload.keys())}"
        )

    result = await db.execute(
        select(User).where(User.auth0_user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Update mutable fields if the token carries newer info
        changed = False
        if not user.subscription_tier:
            user.subscription_tier = "free"
            changed = True
        if email and user.email != email:
            user.email = email
            changed = True
        if name and user.name != name:
            user.name = name
            changed = True
        if picture and user.picture != picture:
            user.picture = picture
            changed = True
        if changed:
            user.updated_at = datetime.utcnow()
            await db.flush()
    else:
        user = User(
            auth0_user_id=user_id,
            email=email,
            name=name,
            picture=picture,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

    return user


async def get_current_user(
    user_id: str = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency to get or create the current authenticated user.
    Uses upsert_user_from_token with a minimal payload
    (only sub is guaranteed when called via verify_token dependency).

    Returns:
        User: The authenticated user model
    """
    return await upsert_user_from_token(db, user_id, {})


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
        token = credentials.credentials
        payload = verifier.verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return await upsert_user_from_token(db, user_id, payload)
    except HTTPException:
        return None


async def get_current_user_with_upsert(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Like get_current_user but passes the full JWT payload to upsert,
    so email/name are synced on every request.
    """
    token = credentials.credentials
    payload = verifier.verify_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: Missing subject claim",
        )
    return await upsert_user_from_token(db, user_id, payload)


async def require_admin(
    current_user: User = Depends(get_current_user_with_upsert),
) -> User:
    """Dependency that requires the authenticated user to be an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def require_paid_or_admin(
    current_user: User = Depends(get_current_user_with_upsert),
) -> User:
    """Dependency that requires the user to have an active paid subscription or be admin."""
    if current_user.is_admin:
        return current_user
    if not current_user.is_paid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires a Pro subscription. Please upgrade to continue.",
        )
    return current_user
