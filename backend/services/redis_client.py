"""
Cliente Redis síncrono compartido, respaldado por un pool de conexiones a nivel
de módulo.

Reutilizado por la lista de revocación de JWT (`security.jwt`) y por el store de
`state`/nonce de OAuth (`routers.oauth`). Evita abrir una conexión TCP nueva en
cada request autenticado o en cada ida-y-vuelta de OAuth.
"""
import redis as redis_sync

from backend.config import settings

_pool = redis_sync.ConnectionPool.from_url(settings.redis_url)


def get_redis() -> redis_sync.Redis:
    """Devuelve un cliente Redis que toma conexiones del pool compartido."""
    return redis_sync.Redis(connection_pool=_pool)
