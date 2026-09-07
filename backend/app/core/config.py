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

    # WhatsApp Cloud API (Meta) — used to send the quotation PDF directly as
    # a document attachment via an approved message template. Create a Meta
    # developer app + WhatsApp Business product, then set these from your
    # app dashboard. Left blank by default; the "Send via WhatsApp" feature
    # returns a clear error until configured.
    WHATSAPP_API_TOKEN: str = ""          # permanent/system-user access token
    WHATSAPP_PHONE_NUMBER_ID: str = ""    # the "Phone number ID" (not the phone number itself)
    WHATSAPP_API_VERSION: str = "v20.0"
    # Name/language of the approved Utility template with a Document header
    # and a 2-variable body (customer name, vehicle model) — see
    # app/modules/quotations/whatsapp.py for exactly how these are used.
    WHATSAPP_TEMPLATE_NAME: str = "quotation_shared"
    WHATSAPP_TEMPLATE_LANG: str = "en_US"

    class Config:
        env_file = ".env"


settings = Settings()