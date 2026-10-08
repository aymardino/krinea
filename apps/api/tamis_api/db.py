"""SQLAlchemy engine and session. PostgreSQL in production, SQLite elsewhere."""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from tamis_api.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        url = get_settings().database_url
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
        _engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk(dbapi_con, _):
                dbapi_con.execute("PRAGMA foreign_keys=ON")
                dbapi_con.execute("PRAGMA journal_mode=WAL")
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def session_factory() -> sessionmaker:
    get_engine()
    return _SessionLocal  # type: ignore[return-value]


def reset_engine() -> None:
    """Tests swap DATABASE_URL between runs."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine, _SessionLocal = None, None


def create_all() -> None:
    from tamis_api import models  # noqa: F401  (registers the tables)
    Base.metadata.create_all(get_engine())


def get_db():
    db: Session = session_factory()()
    try:
        yield db
    finally:
        db.close()
