from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from settings import config


class Database:
    engine = None
    Base = declarative_base()
    _session_factory = None

    @classmethod
    def get_engine(cls):
        if cls.engine is None:
            cls.engine = create_engine(
                config.database_url(),
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=3,
                max_overflow=2,
                pool_timeout=15,
                echo=False,
            )
        return cls.engine

    @classmethod
    def session_factory(cls):
        if cls._session_factory is None:
            cls._session_factory = sessionmaker(
                bind=cls.get_engine(),
                expire_on_commit=False,
            )
        return cls._session_factory

    @classmethod
    def connect_database(cls):
        """Создаёт независимую SQLAlchemy-сессию для одного request/operation."""
        return cls.session_factory()()
