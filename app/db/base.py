from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base. Import model modules before calling metadata operations
    so every table is registered on Base.metadata."""
