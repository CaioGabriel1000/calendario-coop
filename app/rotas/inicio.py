"""Página do calendário mensal."""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import SessaoAutenticada, requer_sessao
from app.db import get_db
from app.calendario import (
    DIAS_SEMANA,
    Mes,
    adicionar_meses,
    mes_da_data,
    montar_grade,
    normalizar_mes,
    ultimo_dia_do_mes,
)
from app.marcacoes import listar_marcacoes, ordenar_marcacoes_grade
from app.relogio import hoje

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def contexto_calendario(mes: Mes, data_hoje, db: Session, usuario_id: int):
    mes_atual = mes_da_data(data_hoje)
    marcacoes_por_data = {}
    for marcacao in listar_marcacoes(
        db,
        data_inicio=date(mes.ano, mes.mes, 1),
        data_fim=ultimo_dia_do_mes(mes),
    ):
        marcacoes_por_data.setdefault(marcacao.data, []).append(marcacao)
    marcacoes_por_data = {
        data: ordenar_marcacoes_grade(marcacoes, usuario_id)
        for data, marcacoes in marcacoes_por_data.items()
    }
    return {
        "mes": mes,
        "mes_anterior": adicionar_meses(mes, -1),
        "mes_seguinte": adicionar_meses(mes, 1),
        "mes_atual": mes_atual,
        "limite_navegacao": adicionar_meses(mes_atual, 12),
        "semanas": montar_grade(mes, data_hoje),
        "dias_semana": DIAS_SEMANA,
        "marcacoes_por_data": marcacoes_por_data,
        "usuario_atual_id": usuario_id,
    }


@router.get("/", response_class=HTMLResponse)
def inicio(
    request: Request,
    mes: str | None = Query(default=None),
    autenticacao: SessaoAutenticada = Depends(requer_sessao),
    db: Session = Depends(get_db),
) -> Response:
    data_hoje = hoje()
    mes_calendario, valido = normalizar_mes(mes, data_hoje)
    if not valido:
        return RedirectResponse(url=f"/?mes={mes_calendario.chave}", status_code=303)

    contexto = contexto_calendario(
        mes_calendario, data_hoje, db, autenticacao.usuario.id
    )
    contexto.update(
        {
            "request": request,
            "apelido": autenticacao.usuario.apelido,
            "csrf_token": autenticacao.sessao.csrf_token,
        }
    )
    return templates.TemplateResponse(
        request=request,
        name="calendario.html",
        context=contexto,
    )
