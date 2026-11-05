from sqlalchemy.engine import make_url

from app.config import get_settings


def test_senha_com_arroba_e_escapada_na_url_padrao(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_PASSWORD", "senha@segura")
    get_settings.cache_clear()
    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    url = make_url(settings.database_url)
    assert url.password == "senha@segura"
    assert url.host == "localhost"
