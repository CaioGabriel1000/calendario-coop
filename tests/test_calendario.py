from datetime import date, datetime, timedelta, timezone
import re

import pytest
from sqlalchemy import select

from app.auth import hash_token
from app.calendario import (
    DIAS_SEMANA,
    Mes,
    dentro_da_janela_editavel,
    montar_grade,
    normalizar_mes,
)
from app.models import Sessao, Usuario
from app.senhas import gerar_hash


@pytest.mark.parametrize(
    ("ano", "mes", "quantidade_dias"),
    [
        (2021, 2, 28),
        (2024, 2, 29),
        (2026, 4, 30),
        (2026, 1, 31),
    ],
)
def test_grade_completa_meses_de_28_a_31_dias(ano, mes, quantidade_dias):
    semanas = montar_grade(Mes(ano, mes), date(ano, mes, 15))
    dias = [dia for semana in semanas for dia in semana]
    dias_do_mes = [dia for dia in dias if dia.pertence_ao_mes]

    assert all(len(semana) == 7 for semana in semanas)
    assert len(dias_do_mes) == quantidade_dias
    assert len(semanas) in {4, 5, 6}
    assert semanas[0][0].data.weekday() == 6
    assert semanas[-1][-1].data.weekday() == 5


def test_grade_comeca_no_domingo_e_completa_sobras_de_outros_meses():
    semanas = montar_grade(Mes(2021, 8), date(2021, 8, 10))
    dias = [dia for semana in semanas for dia in semana]

    assert DIAS_SEMANA[0] == "Dom"
    assert semanas[0][0].data == date(2021, 8, 1)
    assert semanas[-1][-1].data == date(2021, 9, 4)
    assert all(dia.pertence_ao_mes for dia in semanas[0])
    assert not dias[-1].pertence_ao_mes


def test_destaques_de_hoje_e_dia_passado():
    semanas = montar_grade(Mes(2026, 9), date(2026, 9, 28))
    dias = [dia for semana in semanas for dia in semana]
    ontem = next(dia for dia in dias if dia.data == date(2026, 9, 27))
    hoje = next(dia for dia in dias if dia.data == date(2026, 9, 28))

    assert ontem.passado
    assert not ontem.hoje
    assert hoje.hoje
    assert not hoje.passado


def test_limite_de_navegacao_e_mes_invalido():
    data_hoje = date(2026, 9, 28)

    assert normalizar_mes("2027-09", data_hoje) == (Mes(2027, 9), True)
    assert normalizar_mes("2027-10", data_hoje) == (Mes(2027, 9), False)
    assert normalizar_mes("2020-01", data_hoje) == (Mes(2020, 1), True)
    assert normalizar_mes("2026-13", data_hoje) == (Mes(2026, 9), False)


def test_janela_editavel_termina_no_fim_do_mes_atual_mais_12():
    hoje = date(2026, 9, 28)

    assert dentro_da_janela_editavel(hoje, hoje)
    assert dentro_da_janela_editavel(date(2027, 9, 30), hoje)
    assert not dentro_da_janela_editavel(date(2027, 10, 1), hoje)
    assert not dentro_da_janela_editavel(date(2026, 9, 27), hoje)


def autenticar(client, db_session):
    usuario = Usuario(
        email="calendario@example.com",
        nome="Usuária Teste",
        apelido="Calendario",
        senha_hash=gerar_hash("senha-segura"),
    )
    db_session.add(usuario)
    db_session.flush()
    token = "sessao-calendario-valida"
    db_session.add(
        Sessao(
            usuario_id=usuario.id,
            token_hash=hash_token(token),
            csrf_token="csrf-calendario",
            expira_em=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    db_session.flush()
    client.cookies.set("sessao", token)


def test_calendario_mostra_mes_atual_e_controles_htmx(client, db_session, monkeypatch):
    autenticar(client, db_session)
    monkeypatch.setattr("app.rotas.inicio.hoje", lambda: date(2026, 9, 28))

    resposta = client.get("/", follow_redirects=False)

    assert resposta.status_code == 200
    assert '<h1 id="mes-titulo">Setembro 2026</h1>' in resposta.text
    assert 'hx-get="/grade?mes=2026-10"' in resposta.text
    assert 'hx-target="#grade-container"' in resposta.text
    assert 'id="controle-hoje"' in resposta.text
    assert 'data-date="2026-09-28"' in resposta.text
    assert 'calendario-dia-hoje' in resposta.text
    assert "Calendario" in resposta.text
    assert "Sair" in resposta.text


def test_grade_htmx_atualiza_mes_e_controles(client, db_session, monkeypatch):
    autenticar(client, db_session)
    monkeypatch.setattr("app.rotas.calendario.hoje", lambda: date(2026, 9, 28))

    resposta = client.get(
        "/grade?mes=2026-10",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    assert resposta.status_code == 200
    assert 'id="grade-container"' in resposta.text
    assert 'hx-swap-oob="innerHTML">Outubro 2026' in resposta.text
    assert 'hx-swap-oob="outerHTML"' in resposta.text
    assert 'data-date="2026-10-01"' in resposta.text


@pytest.mark.parametrize("valor", ["2026-13", "2027-10", "sem-mes"])
def test_mes_invalido_em_htmx_retorna_400(client, db_session, monkeypatch, valor):
    autenticar(client, db_session)
    monkeypatch.setattr("app.rotas.calendario.hoje", lambda: date(2026, 9, 28))

    resposta = client.get(
        f"/grade?mes={valor}",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    assert resposta.status_code == 400


def test_mes_invalido_na_pagina_redireciona_para_mes_valido(client, db_session, monkeypatch):
    autenticar(client, db_session)
    monkeypatch.setattr("app.rotas.inicio.hoje", lambda: date(2026, 9, 28))

    resposta = client.get("/?mes=2027-10", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/?mes=2027-09"


def test_polling_atualiza_somente_grade_e_pausa_em_aba_oculta(
    client, db_session, monkeypatch
):
    autenticar(client, db_session)
    data_hoje = date(2026, 9, 28)
    monkeypatch.setattr("app.rotas.inicio.hoje", lambda: data_hoje)
    monkeypatch.setattr("app.rotas.calendario.hoje", lambda: data_hoje)

    pagina = client.get("/")
    polling = client.get(
        "/grade?mes=2026-09&somente_grade=1",
        headers={"HX-Request": "true"},
    )

    assert pagina.status_code == polling.status_code == 200
    assert "every 30s [document.visibilityState === 'visible']" in pagina.text
    assert "somente_grade=1" in pagina.text
    assert 'id="grade-container"' in polling.text
    assert 'id="mes-titulo"' not in polling.text
    assert 'id="controle-anterior"' not in polling.text
    assert 'hx-swap-oob' not in polling.text
    assert 'id="painel-dia"' not in polling.text
    assert 'id="painel-host"' in pagina.text


def test_sessao_expirada_durante_polling_redireciona_para_login(
    client, db_session
):
    autenticar(client, db_session)
    sessao = db_session.scalar(select(Sessao))
    assert sessao is not None
    sessao.expira_em = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.flush()

    resposta = client.get(
        "/grade?mes=2026-09&somente_grade=1",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    assert resposta.status_code == 401
    assert resposta.headers["HX-Redirect"] == "/login"
