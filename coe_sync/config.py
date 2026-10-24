import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory for the application
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base application configuration."""

    SECRET_KEY = os.environ.get(
        "SECRET_KEY", "coe-sync-2026-default-secret-key-bulsu-cpe"
    )

    # Database URI default: local SQLite database inside the project directory
    _default_sqlite_path = BASE_DIR / "coe_sync.db"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{_default_sqlite_path.as_posix()}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Engine options for connection resilience
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # SQLite connection settings (for offline parity)
    IS_SQLITE = SQLALCHEMY_DATABASE_URI.startswith("sqlite")

    # Feature Flag: Show demo credential hints on Login Gateway
    SHOW_DEMO_CREDENTIALS = (
        os.environ.get("SHOW_DEMO_CREDENTIALS", "True").lower() == "true"
    )


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    ENV = "development"


class TestingConfig(Config):
    """Testing configuration with in-memory SQLite."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    ENV = "production"


# Mapping for easy environment selection
config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
