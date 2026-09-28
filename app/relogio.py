"""Funções de data e hora no fuso configurado."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings


def hoje() -> date:
    """Retorna a data atual no fuso definido por ``TZ``."""
    return datetime.now(ZoneInfo(get_settings().tz)).date()


def agora_utc() -> datetime:
    """Retorna o instante atual em UTC; substituível em testes."""
    return datetime.now(timezone.utc)
