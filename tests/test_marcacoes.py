from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import hash_token
from app.db import get_db
from app.main import app
from app.marcacoes import registrar_marcacao
from app.models import Marcacao, Sessao, StatusMarcacao, Usuario
from app.senhas import gerar_hash
from apoio import telefone_de_teste

HOJE_TESTE = date(2026, 9, 28)


def criar_usuario_e_sessao(db_session, *, email, apelido):
    usuario = Usuario(
        email=email,
        telefone=telefone_de_teste(email),
        nome=apelido,
        apelido=apelido,
        senha_hash=gerar_hash("senha-segura"),
    )
    db_session.add(usuario)
    db_session.flush()
    token = f"sessao-{apelido.lower()}"
    csrf = f"csrf-{apelido.lower()}"
    db_session.add(
        Sessao(
            usuario_id=usuario.id,
            token_hash=hash_token(token),
            csrf_token=csrf,
            expira_em=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    db_session.flush()
    return usuario, token, csrf


def cliente_autenticado(client, token):
    client.cookies.set("sessao", token)


def enviar_marcacao(client, data, csrf, status):
    return client.put(
        f"/dias/{data.isoformat()}/marcacao",
        data={"status": status},
        headers={"X-CSRF-Token": csrf, "HX-Request": "true"},
    )


def test_upsert_troca_status_sem_criar_segunda_marcacao(
    client, db_session, monkeypatch
):
    monkeypatch.setattr("app.rotas.calendario.hoje", lambda: HOJE_TESTE)
    usuario, token, csrf = criar_usuario_e_sessao(
        db_session, email="ana@example.com", apelido="Ana"
    )
    cliente_autenticado(client, token)
    data = HOJE_TESTE

    primeira = enviar_marcacao(client, data, csrf, "disponivel")
    segunda = enviar_marcacao(client, data, csrf, "indisponivel")

    marcacoes = list(db_session.scalars(select(Marcacao)).all())
    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert len(marcacoes) == 1
    assert marcacoes[0].usuario_id == usuario.id
    assert marcacoes[0].status is StatusMarcacao.INDISPONIVEL
    assert '<dialog id="painel-dia"' in segunda.text
    assert 'hx-swap-oob="outerHTML"' in segunda.text
    assert "Remover marcação" in segunda.text


def test_usuarios_compartilham_marcacoes_e_painel_ordena_por_status(
    client, db_session, monkeypatch
):
    monkeypatch.setattr("app.rotas.calendario.hoje", lambda: HOJE_TESTE)
    ana, ana_token, ana_csrf = criar_usuario_e_sessao(
        db_session, email="ana@example.com", apelido="Ana"
    )
    beatriz, _, _ = criar_usuario_e_sessao(
        db_session, email="bia@example.com", apelido="Beatriz"
    )
    carlos, _, _ = criar_usuario_e_sessao(
        db_session, email="carlos@example.com", apelido="Carlos"
    )
    zeca, zeca_token, zeca_csrf = criar_usuario_e_sessao(
        db_session, email="zeca@example.com", apelido="Zeca"
    )
    data = date(2026, 10, 13)
    cliente_autenticado(client, ana_token)
    with TestClient(app) as zeca_client:
        cliente_autenticado(zeca_client, zeca_token)
        marcar_ana = enviar_marcacao(client, data, ana_csrf, "indisponivel")
        marcar_zeca = enviar_marcacao(zeca_client, data, zeca_csrf, "disponivel")

        registrar_marcacao(
            db_session,
            usuario_id=beatriz.id,
            data=data,
            status=StatusMarcacao.DISPONIVEL,
            data_hoje=HOJE_TESTE,
        )
        registrar_marcacao(
            db_session,
            usuario_id=carlos.id,
            data=data,
            status=StatusMarcacao.INDISPONIVEL,
            data_hoje=HOJE_TESTE,
        )
        painel_ana = client.get(f"/dias/{data.isoformat()}")
        painel_zeca = zeca_client.get(f"/dias/{data.isoformat()}")
        grade = zeca_client.get("/?mes=2026-10")

    assert marcar_ana.status_code == marcar_zeca.status_code == 200
    assert painel_ana.status_code == painel_zeca.status_code == 200
    for resposta in (painel_ana, painel_zeca):
        assert "Terça-feira, 13 de outubro de 2026" in resposta.text
        assert "marcacao-disponivel" in resposta.text
        assert "marcacao-indisponivel" in resposta.text
    ordem = [
        painel_ana.text.index("Ana"),
        painel_ana.text.index("Beatriz"),
        painel_ana.text.index("Zeca"),
        painel_ana.text.index("Carlos"),
    ]
    assert ordem == sorted(ordem)
    assert 'id="celula-2026-10-13"' in grade.text
    assert "marcacao-disponivel" in grade.text
    assert "marcacao-indisponivel" in grade.text


def test_remocao_idempotente_e_limitada_ao_usuario_da_sessao(
    client, db_session, monkeypatch
):
    monkeypatch.setattr("app.rotas.calendario.hoje", lambda: HOJE_TESTE)
    ana, ana_token, ana_csrf = criar_usuario_e_sessao(
        db_session, email="ana@example.com", apelido="Ana"
    )
    bia, bia_token, bia_csrf = criar_usuario_e_sessao(
        db_session, email="bia@example.com", apelido="Bia"
    )
    data = date(2026, 10, 13)
    cliente_autenticado(client, ana_token)
    with TestClient(app) as bia_client:
        cliente_autenticado(bia_client, bia_token)
        enviar_marcacao(client, data, ana_csrf, "disponivel")
        enviar_marcacao(bia_client, data, bia_csrf, "indisponivel")

        primeira_remocao = client.delete(
            f"/dias/{data.isoformat()}/marcacao",
            headers={"X-CSRF-Token": ana_csrf, "HX-Request": "true"},
        )
        segunda_remocao = client.delete(
            f"/dias/{data.isoformat()}/marcacao",
            headers={"X-CSRF-Token": ana_csrf, "HX-Request": "true"},
        )

    marcacoes = list(db_session.scalars(select(Marcacao)).all())
    assert primeira_remocao.status_code == segunda_remocao.status_code == 200
    assert len(marcacoes) == 1
    assert marcacoes[0].usuario_id == bia.id
    assert marcacoes[0].usuario_id != ana.id


def test_dia_passado_e_somente_leitura_e_mutacao_retorna_403(
    client, db_session, monkeypatch
):
    monkeypatch.setattr("app.rotas.calendario.hoje", lambda: HOJE_TESTE)
    usuario, token, csrf = criar_usuario_e_sessao(
        db_session, email="ana@example.com", apelido="Ana"
    )
    cliente_autenticado(client, token)
    ontem = date(2026, 9, 27)
    painel = client.get(f"/dias/{ontem.isoformat()}")
    resposta = enviar_marcacao(client, ontem, csrf, "disponivel")

    assert painel.status_code == 200
    assert "Ninguém marcou este dia ainda." in painel.text
    assert "acoes-marcacao" not in painel.text
    assert resposta.status_code == 403
    assert "Data fora da janela editável." in resposta.text
    assert not list(db_session.scalars(select(Marcacao)).all())


def test_hoje_e_limite_final_sao_editaveis_mas_dia_seguinte_nao(
    client, db_session, monkeypatch
):
    monkeypatch.setattr("app.rotas.calendario.hoje", lambda: HOJE_TESTE)
    _, token, csrf = criar_usuario_e_sessao(
        db_session, email="ana@example.com", apelido="Ana"
    )
    cliente_autenticado(client, token)

    hoje_resposta = enviar_marcacao(client, HOJE_TESTE, csrf, "disponivel")
    fim_janela = date(2027, 9, 30)
    limite_resposta = enviar_marcacao(client, fim_janela, csrf, "indisponivel")
    fora_resposta = enviar_marcacao(
        client, date(2027, 10, 1), csrf, "disponivel"
    )

    assert hoje_resposta.status_code == limite_resposta.status_code == 200
    assert fora_resposta.status_code == 403
    marcacoes = list(db_session.scalars(select(Marcacao)).all())
    assert {marcacao.data for marcacao in marcacoes} == {HOJE_TESTE, fim_janela}
