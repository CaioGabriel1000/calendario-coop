"""Configuração carregada de variáveis de ambiente."""

from dataclasses import dataclass
from functools import lru_cache
import os


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    dominio: str
    postgres_db: str
    postgres_user: str
    postgres_password: str
    database_url: str
    test_database_url: str
    tz: str
    sessao_dias: int
    login_max_falhas: int
    login_bloqueio_minutos: int
    cookie_secure: bool


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    postgres_db = os.getenv("POSTGRES_DB", "calendario")
    postgres_user = os.getenv("POSTGRES_USER", "calendario")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "local_dev_only")
    default_url = (
        f"postgresql+psycopg://{postgres_user}:{postgres_password}"
        f"@localhost:5432/{postgres_db}"
    )
    return Settings(
        dominio=os.getenv("DOMINIO", "localhost"),
        postgres_db=postgres_db,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
        database_url=os.getenv("DATABASE_URL", default_url),
        test_database_url=os.getenv(
            "TEST_DATABASE_URL",
            default_url.rsplit("/", 1)[0] + "/calendario_test",
        ),
        tz=os.getenv("TZ", "America/Sao_Paulo"),
        sessao_dias=int(os.getenv("SESSAO_DIAS", "30")),
        login_max_falhas=int(os.getenv("LOGIN_MAX_FALHAS", "5")),
        login_bloqueio_minutos=int(os.getenv("LOGIN_BLOQUEIO_MINUTOS", "15")),
        cookie_secure=_bool_env("COOKIE_SECURE", True),
    )
