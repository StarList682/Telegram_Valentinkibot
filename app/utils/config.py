import hashlib
import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from config import ADMIN_ID, TOKEN


def _db_name_from_token(token: str) -> str:
    h = hashlib.sha256(token.encode()).hexdigest()[:12]
    return f"anonchat_{h}.sqlite3"


load_dotenv(Path(".env"))


def _get_env(name: str, default: Any) -> Any:
    return os.getenv(name, default)


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_json_list(value: Any) -> list[int]:
    if isinstance(value, list):
        return [int(item) for item in value]
    if value in (None, ""):
        return []
    return [int(item) for item in json.loads(value)]


class BaseSettings:
    pass


@dataclass
class DB(BaseSettings):
    url: str = field(
        default_factory=lambda: _get_env(
            "DB_URL",
            f"sqlite+aiosqlite:///{_db_name_from_token(TOKEN)}",
        )
    )
    host: str = field(default_factory=lambda: _get_env("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(_get_env("DB_PORT", 5432)))
    name: str = field(default_factory=lambda: _get_env("DB_NAME", "anonchat"))
    user: str = field(default_factory=lambda: _get_env("DB_USER", "anonbot"))
    password: str = field(default_factory=lambda: _get_env("DB_PASSWORD", ""))


@dataclass
class Redis(BaseSettings):
    host: str = field(default_factory=lambda: _get_env("REDIS_HOST", "localhost"))
    db: int = field(default_factory=lambda: int(_get_env("REDIS_DB", 0)))


@dataclass
class Bot(BaseSettings):
    token: str = field(default_factory=lambda: _get_env("BOT_TOKEN", TOKEN))
    timezone: str = field(default_factory=lambda: _get_env("BOT_TIMEZONE", "Asia/Yerevan"))
    admins: list[int] = field(
        default_factory=lambda: _parse_json_list(
            _get_env("BOT_ADMINS", f"[{ADMIN_ID}]")
        )
    )
    moders: list[int] = field(
        default_factory=lambda: _parse_json_list(_get_env("BOT_MODERS", "[]"))
    )
    use_redis: bool = field(
        default_factory=lambda: _parse_bool(_get_env("BOT_USE_REDIS", False))
    )


@dataclass
class Payments(BaseSettings):
    enabled: bool = field(
        default_factory=lambda: _parse_bool(_get_env("PAYMENTS_ENABLED", False))
    )
    token: str = field(default_factory=lambda: _get_env("PAYMENTS_TOKEN", ""))
    fiat: str = field(default_factory=lambda: _get_env("PAYMENTS_FIAT", "RUB"))
    accepted_assets: str = field(
        default_factory=lambda: _get_env(
            "PAYMENTS_ACCEPTED_ASSETS",
            "USDT,TON,BTC,ETH,LTC,BNB,TRX,USDC",
        )
    )
    platega_enabled: bool = field(
        default_factory=lambda: _parse_bool(
            _get_env("PAYMENTS_PLATEGA_ENABLED", False)
        )
    )
    platega_base_url: str = field(
        default_factory=lambda: _get_env(
            "PAYMENTS_PLATEGA_BASE_URL",
            "https://app.platega.io",
        )
    )
    platega_merchant_id: str = field(
        default_factory=lambda: _get_env("PAYMENTS_PLATEGA_MERCHANT_ID", "")
    )
    platega_secret: str = field(
        default_factory=lambda: _get_env("PAYMENTS_PLATEGA_SECRET", "")
    )
    platega_return_url: str = field(
        default_factory=lambda: _get_env("PAYMENTS_PLATEGA_RETURN_URL", "")
    )
    platega_failed_url: str = field(
        default_factory=lambda: _get_env("PAYMENTS_PLATEGA_FAILED_URL", "")
    )
    platega_currency: str = field(
        default_factory=lambda: _get_env("PAYMENTS_PLATEGA_CURRENCY", "RUB")
    )
    platega_method: int = field(
        default_factory=lambda: int(_get_env("PAYMENTS_PLATEGA_METHOD", 2))
    )
    api_id: int = field(default_factory=lambda: int(_get_env("PAYMENTS_API_ID", 0)))
    api_key: str = field(default_factory=lambda: _get_env("PAYMENTS_API_KEY", ""))
    project_id: int = field(
        default_factory=lambda: int(_get_env("PAYMENTS_PROJECT_ID", 0))
    )
    project_secret: str = field(
        default_factory=lambda: _get_env("PAYMENTS_PROJECT_SECRET", "")
    )


@dataclass
class Flyer(BaseSettings):
    key: str = field(default_factory=lambda: _get_env("FLYER_KEY", ""))
    base_url: str = field(
        default_factory=lambda: _get_env(
            "FLYER_BASE_URL",
            "https://api.flyerservice.io",
        )
    )


@dataclass
class Settings(BaseSettings):
    bot: Bot = field(default_factory=Bot)
    db: DB = field(default_factory=DB)
    redis: Redis = field(default_factory=Redis)
    payments: Payments = field(default_factory=Payments)
    flyer: Flyer = field(default_factory=Flyer)


@lru_cache
def load_config() -> Settings:
    return Settings()
