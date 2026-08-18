from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — point this at your Postgres instance
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/sk_crm"

    # JWT
    JWT_SECRET: str = "change-me-in-production"  # override via env
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS — the Vite dev server
    CORS_ORIGINS: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
