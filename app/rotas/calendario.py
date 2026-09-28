"""Fragmentos HTMX da navegação do calendário."""

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth import SessaoAutenticada, requer_sessao
from app.rotas.inicio import contexto_calendario
from app.relogio import hoje
from app.calendario import normalizar_mes

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/grade", response_class=HTMLResponse)
def grade(
    request: Request,
    mes: str | None = Query(default=None),
    autenticacao: SessaoAutenticada = Depends(requer_sessao),
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

    contexto = contexto_calendario(mes_calendario, data_hoje)
    contexto.update({"request": request, "oob": True})
    return templates.TemplateResponse(
        request=request,
        name="parciais/grade.html",
        context=contexto,
    )
