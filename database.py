from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from settings import config

class Database:
    engine = None
    Base = declarative_base()

    @classmethod
    def get_engine(cls):
        if cls.engine is None:
            cls.engine = create_engine(
                config.database_url(),
                pool_pre_ping=True,      # Проверка соединения перед использованием
                pool_recycle=180,        # Пересоздавать каждые 3 минуты
                pool_size=5,             # Размер пула
                max_overflow=10,         # Дополнительные соединения при нагрузке
                pool_timeout=30,         # Таймаут ожидания соединения
                echo=False               # Удобно для отладки (можно включить True)
            )
        return cls.engine

    @classmethod
    def connect_database(cls):
        """Создаёт новую сессию."""
        return sessionmaker(bind=cls.get_engine())()