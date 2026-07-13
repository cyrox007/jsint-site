from calendar import c
import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key-for-development")
    ADMIN_ROUTE_PREFIX = os.getenv('ADMIN_ROUTE_PREFIX', '/x321/dashboard')

    # Путь к проекту
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # Путь к базе данных
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "js")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

    def database_url(self, async_mode=False):
        driver = "postgresql+asyncpg" if async_mode else "postgresql"
        return f"{driver}://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
     # Redis
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')


config = Config()