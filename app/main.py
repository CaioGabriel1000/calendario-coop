"""Criação da aplicação FastAPI."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.rotas.auth import router as auth_router
from app.rotas.calendario import router as calendario_router
from app.rotas.health import router as health_router
from app.rotas.inicio import router as inicio_router
from app.rotas.senha import router as senha_router

APP_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Calendário Coop")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.include_router(auth_router)
app.include_router(calendario_router)
app.include_router(health_router)
app.include_router(inicio_router)
app.include_router(senha_router)
