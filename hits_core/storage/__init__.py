"""Storage package with Redis and file backends."""

from .base import BaseStorage
from .file_store import FileStorage

try:
    from .redis_store import RedisStorage
except ImportError:
    RedisStorage = None  # redis not installed, optional

__all__ = [
    "BaseStorage",
    "FileStorage",
]
if RedisStorage is not None:
    __all__.append("RedisStorage")
