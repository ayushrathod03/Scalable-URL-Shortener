from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/url_shortener"
    
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    
    RATE_LIMIT_WINDOW: int = 60  # seconds
    RATE_LIMIT_MAX: int = 10     # requests
    
    CACHE_TTL: int = 86400       # seconds (24 hours)
    
    BLOOM_FILTER_SIZE: int = 1000000  # number of bits
    BLOOM_FILTER_KEY: str = "bloom_filter:urls"
    
    class Config:
        env_file = ".env"

settings = Settings()
