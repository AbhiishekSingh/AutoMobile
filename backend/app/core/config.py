from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — point this at your Postgres instance
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/sk_crm"

    # JWT
    JWT_SECRET: str = "change-me-in-production"  # override via env
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Public address customers use to reach the API (no trailing slash). Used to build
    # the "I AGREE" links sent to customers, e.g. https://crm.skautomobiles.in/api
    PUBLIC_API_URL: str = "http://localhost:8000"

    # Google review link printed on the delivery receipt (leave empty until you have it)
    GOOGLE_REVIEW_URL: str = ""

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
    # Delivery-status webhook (Meta calls /webhooks/whatsapp). VERIFY_TOKEN = any secret you also enter in Meta;
    # APP_SECRET (optional) lets the server check Meta's signature on each call.
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""
    # Approved template names, one per message type (see docs/whatsapp_templates.md for the text + variables)
    WA_TPL_WELCOME: str = "customer_welcome"
    WA_TPL_RECEIPT: str = "booking_receipt"
    WA_TPL_INSURANCE: str = "insurance_policy"
    WA_TPL_DELIVERY: str = "delivery_receipt"
    WA_TPL_ENGAGEMENT: str = "delivery_engagement"
    WA_TPL_REVIEW: str = "google_review_request"
    WA_REVIEW_PARAMS: int = 1     # 1 = old template (link only); 4 = new template: showroom, review link, KTM app link, Instagram link
    WA_TPL_TEST_RIDE: str = "test_ride_scheduled"

    # Email (SMTP) — stopgap for "Send via WhatsApp" while the Meta production
    # template is pending approval (~1 week). Works with Gmail (use an App
    # Password, not your normal password), your business mailbox, or any
    # standard SMTP provider. Left blank by default; the "Send via Email"
    # feature returns a clear error until configured, same pattern as WhatsApp.
    EMAIL_SMTP_HOST: str = ""              # e.g. "smtp.gmail.com"
    EMAIL_SMTP_PORT: int = 587              # 587 = STARTTLS (most common), 465 = SSL
    EMAIL_SMTP_USERNAME: str = ""
    EMAIL_SMTP_PASSWORD: str = ""
    EMAIL_FROM_ADDRESS: str = ""            # e.g. "S.K Automobiles <no-reply@skautomobiles.in>"
    EMAIL_USE_SSL: bool = False              # set True if using port 465 instead of 587

    # Customer document uploads (Aadhaar, PAN, ...). Files are stored on the
    # backend server's disk under UPLOAD_DIR (relative to where uvicorn runs).
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 5                 # per file

    class Config:
        env_file = ".env"


settings = Settings()