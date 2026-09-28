"""Fragmentos HTMX da navegação do calendário."""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import SessaoAutenticada, requer_csrf, requer_sessao
from app.calendario import (
    data_por_extenso,
    dentro_da_janela_editavel,
    mes_da_data,
    montar_grade,
    normalizar_mes,
)
from app.db import get_db
from app.marcacoes import (
    DataForaDaJanelaError,
    listar_marcacoes,
    ordenar_marcacoes_grade,
    ordenar_marcacoes_painel,
    registrar_marcacao,
    remover_marcacao,
)
from app.models import StatusMarcacao
from app.rotas.inicio import contexto_calendario
from app.relogio import hoje

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/grade", response_class=HTMLResponse)
def grade(
    request: Request,
    mes: str | None = Query(default=None),
    autenticacao: SessaoAutenticada = Depends(requer_sessao),
    db: Session = Depends(get_db),
) -> Response:
    data_hoje = hoje()
    mes_calendario, valido = normalizar_mes(mes, data_hoje)
    if not valido:
        if request.headers.get("HX-Request", "").lower() == "true":
            return HTMLResponse(
                content="Mês inválido ou fora do limite de navegação.",
                status_code=400,
            )
        return RedirectResponse(url=f"/?mes={mes_calendario.chave}", status_code=303)

    contexto = contexto_calendario(
        mes_calendario, data_hoje, db, autenticacao.usuario.id
    )
    contexto.update({"request": request, "oob": True})
    return templates.TemplateResponse(
        request=request,
        name="parciais/grade.html",
        context=contexto,
    )


def contexto_painel(
    request: Request,
    db: Session,
    data: date,
    autenticacao: SessaoAutenticada,
    data_hoje: date,
    *,
    erro: str | None = None,
) -> dict:
    marcacoes = listar_marcacoes(db, data_inicio=data, data_fim=data)
    return {
        "request": request,
        "data": data,
        "data_extenso": data_por_extenso(data),
        "marcacoes": ordenar_marcacoes_painel(
            marcacoes, autenticacao.usuario.id
        ),
        "marcacoes_celula": ordenar_marcacoes_grade(
            marcacoes, autenticacao.usuario.id
        ),
        "usuario_atual_id": autenticacao.usuario.id,
        "csrf_token": autenticacao.sessao.csrf_token,
        "pode_editar": dentro_da_janela_editavel(data, data_hoje),
        "erro": erro,
        "dia": next(
            dia
            for semana in montar_grade(mes_da_data(data), data_hoje)
            for dia in semana
            if dia.data == data
        ),
    }


def resposta_painel_e_celula(
    request: Request,
    db: Session,
    data: date,
    autenticacao: SessaoAutenticada,
    data_hoje: date,
    *,
    erro: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    contexto = contexto_painel(
        request, db, data, autenticacao, data_hoje, erro=erro
    )
    painel = templates.get_template("parciais/painel_dia.html").render(contexto)
    celula_contexto = {
        **contexto,
        "dia": contexto["dia"],
        "marcacoes_por_data": {data: contexto["marcacoes_celula"]},
        "oob_celula": True,
    }
    celula = templates.get_template("parciais/celula.html").render(celula_contexto)
    return HTMLResponse(content=painel + celula, status_code=status_code)


@router.get("/dias/{data}", response_class=HTMLResponse)
def painel_dia(
    request: Request,
    data: date,
    autenticacao: SessaoAutenticada = Depends(requer_sessao),
    db: Session = Depends(get_db),
) -> Response:
    contexto = contexto_painel(request, db, data, autenticacao, hoje())
    return templates.TemplateResponse(
        request=request,
        name="parciais/painel_dia.html",
        context=contexto,
    )


@router.put("/dias/{data}/marcacao", response_class=HTMLResponse)
def atualizar_marcacao(
    request: Request,
    data: date,
    status: StatusMarcacao = Form(...),
    autenticacao: SessaoAutenticada = Depends(requer_csrf),
    db: Session = Depends(get_db),
) -> Response:
    data_hoje = hoje()
    try:
        registrar_marcacao(
            db,
            usuario_id=autenticacao.usuario.id,
            data=data,
            status=status,
            data_hoje=data_hoje,
        )
    except DataForaDaJanelaError as exc:
        return resposta_painel_e_celula(
            request,
            db,
            data,
            autenticacao,
            data_hoje,
            erro=str(exc),
            status_code=403,
        )
    return resposta_painel_e_celula(
        request, db, data, autenticacao, data_hoje
    )


@router.delete("/dias/{data}/marcacao", response_class=HTMLResponse)
def excluir_marcacao(
    request: Request,
    data: date,
    autenticacao: SessaoAutenticada = Depends(requer_csrf),
    db: Session = Depends(get_db),
) -> Response:
    data_hoje = hoje()
    try:
        remover_marcacao(
            db,
            usuario_id=autenticacao.usuario.id,
            data=data,
            data_hoje=data_hoje,
        )
    except DataForaDaJanelaError as exc:
        return resposta_painel_e_celula(
            request,
            db,
            data,
            autenticacao,
            data_hoje,
            erro=str(exc),
            status_code=403,
        )
    return resposta_painel_e_celula(
        request, db, data, autenticacao, data_hoje
    )
