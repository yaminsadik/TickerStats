"""
Simple caching interface for deck generation service.
Supports in-memory caching with optional Redis backend.
"""

import hashlib
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional

from app.deck.utils.logging import get_logger

logger = get_logger(__name__)


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: int) -> None:
        """Set value in cache with TTL."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass


class InMemoryCache(CacheBackend):
    """
    Simple in-memory cache with TTL support.
    Suitable for development and single-instance deployments.
    """
    
    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._max_size = max_size
    
    def _is_expired(self, expiry: float) -> bool:
        return time.time() > expiry
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._cache.items() if now > exp]
        for key in expired_keys:
            del self._cache[key]
    
    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache is full."""
        if len(self._cache) >= self._max_size:
            # Remove oldest 10% of entries
            entries = sorted(self._cache.items(), key=lambda x: x[1][1])
            to_remove = len(entries) // 10 or 1
            for key, _ in entries[:to_remove]:
                del self._cache[key]
    
    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        
        value, expiry = self._cache[key]
        if self._is_expired(expiry):
            del self._cache[key]
            return None
        
        logger.debug(f"Cache hit: {key[:50]}")
        return value
    
    def set(self, key: str, value: Any, ttl: int) -> None:
        self._cleanup_expired()
        self._evict_if_needed()
        
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)
        logger.debug(f"Cache set: {key[:50]}, TTL: {ttl}s")
    
    def delete(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        self._cache.clear()
        logger.info("Cache cleared")
    
    def exists(self, key: str) -> bool:
        if key not in self._cache:
            return False
        _, expiry = self._cache[key]
        if self._is_expired(expiry):
            del self._cache[key]
            return False
        return True
    
    def stats(self) -> dict:
        """Get cache statistics."""
        self._cleanup_expired()
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
        }


class RedisCache(CacheBackend):
    """
    Redis-backed cache for distributed deployments.
    Requires redis-py package.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        prefix: str = "deck:",
    ):
        try:
            import redis
            self._client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
            )
            self._prefix = prefix
            # Test connection
            self._client.ping()
            logger.info(f"Connected to Redis at {host}:{port}")
        except ImportError:
            raise RuntimeError("redis package required for RedisCache. Install with: pip install redis")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Redis: {e}")
    
    def _prefixed_key(self, key: str) -> str:
        return f"{self._prefix}{key}"
    
    def get(self, key: str) -> Optional[Any]:
        try:
            value = self._client.get(self._prefixed_key(key))
            if value is None:
                return None
            logger.debug(f"Cache hit: {key[:50]}")
            return json.loads(value)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            self._client.setex(
                self._prefixed_key(key),
                ttl,
                json.dumps(value, default=str),
            )
            logger.debug(f"Cache set: {key[:50]}, TTL: {ttl}s")
        except Exception as e:
            logger.warning(f"Redis set error: {e}")
    
    def delete(self, key: str) -> None:
        try:
            self._client.delete(self._prefixed_key(key))
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")
    
    def clear(self) -> None:
        try:
            # Only clear keys with our prefix
            keys = self._client.keys(f"{self._prefix}*")
            if keys:
                self._client.delete(*keys)
            logger.info("Cache cleared")
        except Exception as e:
            logger.warning(f"Redis clear error: {e}")
    
    def exists(self, key: str) -> bool:
        try:
            return self._client.exists(self._prefixed_key(key)) > 0
        except Exception as e:
            logger.warning(f"Redis exists error: {e}")
            return False


class DeckCache:
    """
    High-level caching interface for deck generation.
    Provides typed methods for common caching patterns.
    """
    
    DEFAULT_TTL = 3600  # 1 hour
    
    def __init__(self, backend: Optional[CacheBackend] = None):
        self._backend = backend or InMemoryCache()
    
    def _build_key(
        self,
        ticker: str,
        section_id: str,
        provider: str,
        model: str,
        constraints_hash: str,
    ) -> str:
        """Build cache key for section generation."""
        return f"section:{ticker}:{section_id}:{provider}:{model}:{constraints_hash}"
    
    def get_section(
        self,
        ticker: str,
        section_id: str,
        provider: str,
        model: str,
        constraints_hash: str,
    ) -> Optional[dict]:
        """Get cached section result."""
        key = self._build_key(ticker, section_id, provider, model, constraints_hash)
        return self._backend.get(key)
    
    def set_section(
        self,
        ticker: str,
        section_id: str,
        provider: str,
        model: str,
        constraints_hash: str,
        result: dict,
        ttl: Optional[int] = None,
    ) -> None:
        """Cache section result."""
        key = self._build_key(ticker, section_id, provider, model, constraints_hash)
        self._backend.set(key, result, ttl or self.DEFAULT_TTL)
    
    def get_comps(self, ticker: str, symbols: list[str]) -> Optional[dict]:
        """Get cached comparables table."""
        symbols_key = "_".join(sorted(symbols))
        key = f"comps:{ticker}:{symbols_key}"
        return self._backend.get(key)
    
    def set_comps(
        self,
        ticker: str,
        symbols: list[str],
        result: dict,
        ttl: Optional[int] = None,
    ) -> None:
        """Cache comparables table."""
        symbols_key = "_".join(sorted(symbols))
        key = f"comps:{ticker}:{symbols_key}"
        self._backend.set(key, result, ttl or 300)  # 5 min default for market data
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._backend.clear()


def cached(
    key_builder: Callable[..., str],
    ttl: int = 3600,
    cache: Optional[DeckCache] = None,
):
    """
    Decorator for caching function results.
    
    Args:
        key_builder: Function to build cache key from arguments
        ttl: Time to live in seconds
        cache: DeckCache instance (uses global if not provided)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _cache = cache or _global_cache
            if _cache is None:
                return func(*args, **kwargs)
            
            key = key_builder(*args, **kwargs)
            
            # Try cache first
            cached_value = _cache._backend.get(key)
            if cached_value is not None:
                return cached_value
            
            # Call function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                _cache._backend.set(key, result, ttl)
            
            return result
        return wrapper
    return decorator


# Global cache instance (initialized lazily)
_global_cache: Optional[DeckCache] = None


def get_cache() -> DeckCache:
    """Get the global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = DeckCache()
    return _global_cache


def init_cache(backend: Optional[CacheBackend] = None) -> DeckCache:
    """Initialize the global cache with a specific backend."""
    global _global_cache
    _global_cache = DeckCache(backend)
    return _global_cache
