# src/config.py
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Infra
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://social_redis:6379/0")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "mongodb://social_mongo:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "social_agent")
    QUEUE_NAME: str = os.getenv("QUEUE_NAME", "social_tasks")

    # Twitter
    TWITTER_USERNAME: str = os.getenv("TWITTER_USERNAME")
    TWITTER_PASSWORD: str = os.getenv("TWITTER_PASSWORD")
    TWITTER_EMAIL: str = os.getenv("TWITTER_EMAIL")
    TWITTER_EMAIL_PASSWORD: str = os.getenv("TWITTER_EMAIL_PASSWORD")
    TWITTER_DB_PATH: str = os.getenv("TWITTER_DB_PATH", "/app/data/accounts.db")

    class Config:
        env_file = ".env"

settings = Settings()