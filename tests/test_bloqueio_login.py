from datetime import datetime, timedelta, timezone
import re

import pytest
from sqlalchemy import select

from app.models import Usuario
from app.usuarios import criar_usuario
from apoio import telefone_de_teste


def fazer_login(client, *, identificador, senha):
    resposta = client.get("/login", follow_redirects=False)
    token = re.search(r'name="csrf_token" value="([^"]+)"', resposta.text)
    assert token is not None
    return client.post(
        "/login",
        data={
            "identificador": identificador,
            "senha": senha,
            "csrf_token": token.group(1),
        },
        follow_redirects=False,
    )


def preparar_usuario(db_session):
    return criar_usuario(
        db_session,
        email="bloqueio@example.com",
        telefone=telefone_de_teste("bloqueio@example.com"),
        nome="Pessoa Teste",
        apelido="Bloqueio",
        senha="senha-segura",
    )


def test_bloqueia_na_quinta_falha_recusa_senha_correta_e_libera_depois(
    client,
    db_session,
    monkeypatch,
):
    usuario = preparar_usuario(db_session)
    instante = [datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr("app.rotas.auth.agora_utc", lambda: instante[0])

    identificadores = [
        "bloqueio@example.com",
        usuario.telefone,
        "bloqueio@example.com",
        usuario.telefone,
        "bloqueio@example.com",
    ]
    for tentativa, identificador in enumerate(identificadores):
        resposta = fazer_login(
            client,
            identificador=identificador,
            senha="senha-incorreta",
        )
        assert resposta.status_code == 200
        if tentativa < 4:
            assert "E-mail, telefone ou senha inválidos." in resposta.text
        else:
            assert "Muitas tentativas. Tente novamente em 15 minutos." in resposta.text

    usuario = db_session.scalar(
        select(Usuario).where(Usuario.email == "bloqueio@example.com")
    )
    assert usuario is not None
    assert usuario.falhas_login == 5
    assert usuario.bloqueado_ate == instante[0] + timedelta(minutes=15)

    bloqueado = fazer_login(
        client,
        identificador="bloqueio@example.com",
        senha="senha-segura",
    )
    bloqueado_por_telefone = fazer_login(
        client,
        identificador=usuario.telefone,
        senha="senha-segura",
    )
    assert bloqueado.status_code == 200
    assert bloqueado_por_telefone.status_code == 200
    assert "Muitas tentativas. Tente novamente em 15 minutos." in bloqueado.text
    assert "Muitas tentativas. Tente novamente em 15 minutos." in bloqueado_por_telefone.text

    instante[0] += timedelta(minutes=15, seconds=1)
    liberado = fazer_login(
        client,
        identificador=usuario.telefone,
        senha="senha-segura",
    )
    assert liberado.status_code == 303

    db_session.refresh(usuario)
    assert usuario.falhas_login == 0
    assert usuario.bloqueado_ate is None


@pytest.mark.parametrize("usar_telefone", [False, True])
def test_login_bem_sucedido_zera_falhas_anteriores(
    client, db_session, usar_telefone
):
    usuario = preparar_usuario(db_session)
    usuario.falhas_login = 3
    db_session.flush()

    resposta = fazer_login(
        client,
        identificador=(
            usuario.telefone if usar_telefone else "bloqueio@example.com"
        ),
        senha="senha-segura",
    )

    assert resposta.status_code == 303
    db_session.refresh(usuario)
    assert usuario.falhas_login == 0
    assert usuario.bloqueado_ate is None


@pytest.mark.parametrize("usar_telefone", [False, True])
def test_cinco_falhas_com_um_identificador_bloqueiam_conta(
    client, db_session, monkeypatch, usar_telefone
):
    usuario = preparar_usuario(db_session)
    instante = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.rotas.auth.agora_utc", lambda: instante)
    identificador = usuario.telefone if usar_telefone else usuario.email

    for _ in range(5):
        resposta = fazer_login(
            client,
            identificador=identificador,
            senha="senha-incorreta",
        )

    assert resposta.status_code == 200
    assert "Muitas tentativas. Tente novamente em 15 minutos." in resposta.text
    db_session.refresh(usuario)
    assert usuario.falhas_login == 5
    assert usuario.bloqueado_ate == instante + timedelta(minutes=15)
