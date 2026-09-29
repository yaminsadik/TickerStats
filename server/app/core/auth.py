"""Auth0 JWT verification and authentication dependencies."""
import logging
import threading
import time
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

# HTTPBearer scheme for extracting JWT from Authorization header
security = HTTPBearer()


class Auth0JWTVerifier:
    """Verifies Auth0 JWT tokens using JWKS."""

    def __init__(self):
        # Validate that AUTH0_DOMAIN looks like an Auth0 tenant domain or custom domain
        if settings.AUTH0_DOMAIN and not (".auth0.com" in settings.AUTH0_DOMAIN or ".auth0.app" in settings.AUTH0_DOMAIN):
            logger.warning(
                f"AUTH0_DOMAIN '{settings.AUTH0_DOMAIN}' is not an Auth0 tenant domain. "
                f"If this is a custom domain, ensure it is fully configured in Auth0 "
                f"and that https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json is reachable."
            )

        self.jwks_url = (
            f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
            if settings.AUTH0_DOMAIN
            else ""
        )
        self._jwks_cache: Optional[dict] = None
        self._jwks_cached_at: float = 0.0
        self._jwks_lock = threading.Lock()

    def _ensure_configured(self) -> None:
        missing = []
        if not settings.AUTH0_DOMAIN:
            missing.append("AUTH0_DOMAIN")
        if not settings.AUTH0_API_AUDIENCE:
            missing.append("AUTH0_API_AUDIENCE")
        if missing:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Auth0 is not configured. Set "
                    f"{', '.join(missing)} in the backend environment."
                ),
            )

    def _is_jwks_cache_stale(self) -> bool:
        if self._jwks_cache is None:
            return True
        age_seconds = time.time() - self._jwks_cached_at
        return age_seconds >= settings.AUTH0_JWKS_CACHE_TTL_SECONDS

    @staticmethod
    def _find_rsa_key(jwks: dict, kid: str) -> Optional[dict]:
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
        return None

    def get_jwks(self, force_refresh: bool = False) -> dict:
        """Fetch and cache Auth0 JWKS (JSON Web Key Set)."""
        self._ensure_configured()

        if not force_refresh and not self._is_jwks_cache_stale():
            return self._jwks_cache or {}

        with self._jwks_lock:
            if not force_refresh and not self._is_jwks_cache_stale():
                return self._jwks_cache or {}
            try:
                response = requests.get(self.jwks_url, timeout=5)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_cached_at = time.time()
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
        return self._jwks_cache or {}

    def verify_token(self, token: str) -> dict:
        """
        Verify JWT token and return decoded payload.

        Raises:
            HTTPException: If token is invalid or expired
        """
        self._ensure_configured()

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
            rsa_key = self._find_rsa_key(jwks, kid)

            # If key is missing, force a JWKS refresh to handle Auth0 key rotation.
            if not rsa_key:
                jwks = self.get_jwks(force_refresh=True)
                rsa_key = self._find_rsa_key(jwks, kid)

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
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed",
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


def _claim(payload: dict, name: str) -> Optional[str]:
    """Read a profile claim from the standard slot or a namespaced custom claim."""
    return (
        payload.get(name)
        or payload.get(f"https://{settings.AUTH0_DOMAIN}/{name}")
        or payload.get(f"https://tickerstats.com/{name}")
        or payload.get(f"http://tickerstats.com/{name}")
    )


async def upsert_user_from_token(db: AsyncSession, user_id: str, payload: dict) -> User:
    """Return the users row for this Auth0 subject, creating it on first login.

    The common case is one SELECT. On first login, INSERT ... ON CONFLICT DO
    NOTHING makes two simultaneous first requests safe: one inserts, the other
    does nothing, and both read the same row back.
    """
    email = _claim(payload, "email")
    name = _claim(payload, "name") or payload.get("nickname")
    picture = _claim(payload, "picture")

    user = await db.get(User, user_id)
    if user is None:
        await db.execute(
            pg_insert(User)
            .values(auth0_user_id=user_id, email=email, name=name, picture=picture)
            .on_conflict_do_nothing(index_elements=[User.auth0_user_id])
        )
        user = await db.get(User, user_id)
        if not email:
            logger.warning("New user %s has no email claim; claims: %s", user_id, list(payload))
        return user

    # Keep profile fields in sync with the identity provider.
    for field, value in (("email", email), ("name", name), ("picture", picture)):
        if value and getattr(user, field) != value:
            setattr(user, field, value)
    await db.flush()
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
    user = await upsert_user_from_token(db, user_id, payload)

    # Set contextvar so request timing middleware can log user_id
    from app.core.middleware import current_user_id_var
    current_user_id_var.set(user.auth0_user_id)

    return user


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
