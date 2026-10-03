from datetime import datetime, timedelta, timezone
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import hash_token
from app.models import Sessao, Usuario
from app.senhas import gerar_hash, verificar_senha
from apoio import telefone_de_teste


def criar_usuario_com_sessoes(db_session, quantidade=1):
    usuario = Usuario(
        email="senha@example.com",
        telefone=telefone_de_teste("senha@example.com"),
        nome="Pessoa Teste",
        apelido="Senha",
        senha_hash=gerar_hash("senha-antiga"),
    )
    db_session.add(usuario)
    db_session.flush()
    credenciais = []
    for indice in range(quantidade):
        token = f"sessao-senha-{indice}"
        csrf = f"csrf-senha-{indice}"
        sessao = Sessao(
            usuario_id=usuario.id,
            token_hash=hash_token(token),
            csrf_token=csrf,
            expira_em=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db_session.add(sessao)
        db_session.flush()
        credenciais.append((sessao, token, csrf))
    return usuario, credenciais


def postar_troca(client, csrf, *, atual, nova, confirmacao):
    return client.post(
        "/senha",
        data={
            "csrf_token": csrf,
            "senha_atual": atual,
            "nova_senha": nova,
            "confirmar_senha": confirmacao,
        },
        follow_redirects=False,
    )


@pytest.mark.parametrize(
    ("atual", "nova", "confirmacao", "mensagem"),
    [
        (
            "senha-errada",
            "senha-nova-segura",
            "senha-nova-segura",
            "A senha atual está incorreta.",
        ),
        (
            "senha-antiga",
            "curta",
            "curta",
            "A nova senha deve ter no mínimo 8 caracteres.",
        ),
        (
            "senha-antiga",
            "senha-nova-segura",
            "outra-senha-segura",
            "A confirmação da nova senha não confere.",
        ),
    ],
)
def test_validacoes_da_troca_de_senha(
    client, db_session, atual, nova, confirmacao, mensagem
):
    usuario, [(sessao, token, csrf)] = criar_usuario_com_sessoes(db_session)
    client.cookies.set("sessao", token)

    resposta = postar_troca(
        client,
        csrf,
        atual=atual,
        nova=nova,
        confirmacao=confirmacao,
    )

    assert resposta.status_code == 200
    assert mensagem in resposta.text
    db_session.refresh(usuario)
    assert verificar_senha(usuario.senha_hash, "senha-antiga")
    assert db_session.scalar(select(Sessao.id).where(Sessao.id == sessao.id)) == sessao.id


def test_troca_mantem_sessao_atual_e_encerra_as_outras(
    client, db_session
):
    usuario, credenciais = criar_usuario_com_sessoes(db_session, quantidade=2)
    sessao_atual, token_atual, csrf_atual = credenciais[0]
    _, token_outro, _ = credenciais[1]
    hash_antigo = usuario.senha_hash
    client.cookies.set("sessao", token_atual)

    with TestClient(client.app) as outro_navegador:
        outro_navegador.cookies.set("sessao", token_outro)
        tela = client.get("/senha")
        resposta = postar_troca(
            client,
            csrf_atual,
            atual="senha-antiga",
            nova="senha-nova-segura",
            confirmacao="senha-nova-segura",
        )

        assert tela.status_code == 200
        assert 'name="senha_atual"' in tela.text
        assert "Alterar senha" in client.get("/").text
        assert resposta.status_code == 200
        assert "Senha alterada." in resposta.text
        assert client.get("/").status_code == 200
        assert outro_navegador.get("/", follow_redirects=False).status_code == 303

        sessoes = list(db_session.scalars(select(Sessao)).all())
        assert len(sessoes) == 1
        assert sessoes[0].id == sessao_atual.id
        db_session.refresh(usuario)
        assert usuario.senha_hash != hash_antigo
        assert verificar_senha(usuario.senha_hash, "senha-nova-segura")
        assert not verificar_senha(usuario.senha_hash, "senha-antiga")

        pagina_login = outro_navegador.get("/login")
        token_csrf = re.search(r'name="csrf_token" value="([^"]+)"', pagina_login.text)
        assert token_csrf is not None
        login = outro_navegador.post(
            "/login",
            data={
                "email": "senha@example.com",
                "senha": "senha-nova-segura",
                "csrf_token": token_csrf.group(1),
            },
            follow_redirects=False,
        )
        assert login.status_code == 303
        assert login.headers["location"] == "/"


def test_tela_de_senha_exige_sessao(client):
    resposta = client.get("/senha", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"
