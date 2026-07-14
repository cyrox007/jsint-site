from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from settings import config

class Database:
    engine = None
    Base = declarative_base()

    @classmethod
    def get_engine(cls):
        if cls.engine is None:
            cls.engine = create_engine(config.database_url())
        return cls.engine

    @classmethod
    def connect_database(cls):
        """Создаёт новую сессию."""
        return sessionmaker(bind=cls.get_engine())()