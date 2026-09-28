import pytest

from app.models import Usuario
from app.usuarios import UsuarioDuplicadoError, criar_usuario


def criar(
    db_session,
    *,
    email="ana@example.com",
    nome="Ana Souza",
    apelido="Ana",
    senha="senha-segura",
):
    return criar_usuario(
        db_session,
        email=email,
        nome=nome,
        apelido=apelido,
        senha=senha,
    )


def test_email_unico_sem_diferenciar_maiusculas(db_session):
    usuario = criar(db_session)

    assert usuario.email == "ana@example.com"
    with pytest.raises(UsuarioDuplicadoError, match="e-mail"):
        criar(db_session, email="ANA@EXAMPLE.COM", apelido="Outra")


def test_apelido_unico_sem_diferenciar_maiusculas_incluindo_desativado(db_session):
    usuario = criar(db_session)
    usuario.ativo = False
    db_session.flush()

    with pytest.raises(UsuarioDuplicadoError, match="apelido"):
        criar(db_session, email="outra@example.com", apelido="aNA")


def test_senha_com_menos_de_oito_caracteres_e_recusada(db_session):
    with pytest.raises(ValueError, match="no mínimo 8"):
        criar(db_session, senha="curta")

    assert db_session.query(Usuario).count() == 0
