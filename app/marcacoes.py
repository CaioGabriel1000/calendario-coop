"""Regras e consultas das marcações de disponibilidade."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.calendario import dentro_da_janela_editavel
from app.models import Marcacao, StatusMarcacao, Usuario


@dataclass(frozen=True, slots=True)
class MarcacaoVisivel:
    data: date
    usuario_id: int
    apelido: str
    status: StatusMarcacao


class DataForaDaJanelaError(ValueError):
    """A data solicitada não pode ser editada neste momento."""


def validar_data_editavel(data: date, data_hoje: date) -> None:
    if not dentro_da_janela_editavel(data, data_hoje):
        raise DataForaDaJanelaError("Data fora da janela editável.")


def registrar_marcacao(
    db: Session,
    *,
    usuario_id: int,
    data: date,
    status: StatusMarcacao,
    data_hoje: date,
) -> None:
    validar_data_editavel(data, data_hoje)
    comando = insert(Marcacao).values(
        usuario_id=usuario_id,
        data=data,
        status=status,
    )
    db.execute(
        comando.on_conflict_do_update(
            index_elements=[Marcacao.usuario_id, Marcacao.data],
            set_={"status": status, "atualizado_em": func.now()},
        )
    )
    db.commit()


def remover_marcacao(
    db: Session,
    *,
    usuario_id: int,
    data: date,
    data_hoje: date,
) -> None:
    validar_data_editavel(data, data_hoje)
    db.execute(
        delete(Marcacao).where(
            Marcacao.usuario_id == usuario_id,
            Marcacao.data == data,
        )
    )
    db.commit()


def listar_marcacoes(
    db: Session,
    *,
    data_inicio: date,
    data_fim: date,
) -> list[MarcacaoVisivel]:
    linhas = db.execute(
        select(Marcacao.data, Marcacao.usuario_id, Usuario.apelido, Marcacao.status)
        .join(Usuario, Usuario.id == Marcacao.usuario_id)
        .where(Marcacao.data >= data_inicio, Marcacao.data <= data_fim)
    ).all()
    return [
        MarcacaoVisivel(
            data=data,
            usuario_id=usuario_id,
            apelido=apelido,
            status=status,
        )
        for data, usuario_id, apelido, status in linhas
    ]


def ordenar_marcacoes_painel(
    marcacoes: list[MarcacaoVisivel], usuario_atual_id: int
) -> list[MarcacaoVisivel]:
    return sorted(
        marcacoes,
        key=lambda item: (
            item.usuario_id != usuario_atual_id,
            0 if item.status is StatusMarcacao.DISPONIVEL else 1,
            item.apelido.casefold(),
        ),
    )


def ordenar_marcacoes_grade(
    marcacoes: list[MarcacaoVisivel], usuario_atual_id: int
) -> list[MarcacaoVisivel]:
    return sorted(
        marcacoes,
        key=lambda item: (
            item.usuario_id != usuario_atual_id,
            item.apelido.casefold(),
        ),
    )
