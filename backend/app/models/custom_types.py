import json
from typing import List, Optional
from sqlalchemy.types import TypeDecorator, JSON, Text
from sqlalchemy.dialects import postgresql

try:
    from pgvector.sqlalchemy import Vector as PGVector
except ImportError:
    PGVector = None


class CompatibleVector(TypeDecorator):
    """
    SQLAlchemy type decorator that uses pgvector's Vector in PostgreSQL
    and falls back to JSON / Text in SQLite for developer/testing environments.
    """
    impl = Text
    cache_ok = True

    def __init__(self, dim: int = 768, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PGVector is not None:
            return dialect.type_descriptor(PGVector(self.dim))
        else:
            return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql" and PGVector is not None:
            return value
        # For SQLite / JSON storage
        if isinstance(value, (list, tuple)):
            return list(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value


# Dialect-adaptive JSON type (JSONB on PostgreSQL, JSON on SQLite)
CompatibleJSON = JSON().with_variant(postgresql.JSONB, "postgresql")
