"""Funções de data e hora no fuso configurado."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def hoje() -> date:
    """Retorna a data atual no fuso definido por ``TZ``."""
    return datetime.now(ZoneInfo(get_settings().tz)).date()
