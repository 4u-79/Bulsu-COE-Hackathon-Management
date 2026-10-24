import os
import socket
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

# Base directory for the application
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / ".env")


def resolve_database_uri() -> str:
    """
    Resolve the database connection string with automated fallback resilience.
    If MySQL is configured in DATABASE_URL, verifies whether the MySQL service is actively listening.
    If unreachable, alerts and smoothly falls back to local SQLite so development never stalls.
    """
    configured_uri = os.environ.get("DATABASE_URL", "").strip()
    _default_sqlite_path = BASE_DIR / "instance" / "coe_sync.db"
    _default_sqlite_uri = f"sqlite:///{_default_sqlite_path.as_posix()}"

    if not configured_uri:
        return _default_sqlite_uri

    if configured_uri.startswith("mysql"):
        try:
            parsed = urlparse(configured_uri)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 3306

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            conn_res = sock.connect_ex((host, port))
            sock.close()

            if conn_res != 0:
                print(
                    f"\n[DATABASE CONFIG WARNING] MySQL service at {host}:{port} is unreachable or down. "
                    f"Falling back smoothly to local SQLite ({_default_sqlite_uri}) so development never stalls.\n",
                    flush=True,
                )
                return _default_sqlite_uri
        except Exception as e:
            print(
                f"\n[DATABASE CONFIG WARNING] Error testing MySQL connection ({e}). "
                f"Falling back to local SQLite ({_default_sqlite_uri}).\n",
                flush=True,
            )
            return _default_sqlite_uri

    if configured_uri == "sqlite:///coe_sync.db":
        return _default_sqlite_uri

    return configured_uri


class Config:
    """Base application configuration."""

    SECRET_KEY = os.environ.get(
        "SECRET_KEY", "coe-sync-2026-default-secret-key-bulsu-cpe"
    )

    SQLALCHEMY_DATABASE_URI = resolve_database_uri()

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
