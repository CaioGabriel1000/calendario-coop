"""Montagem do calendário mensal e limites de navegação."""

from dataclasses import dataclass
from datetime import date, timedelta
import re

from app.relogio import hoje as data_de_hoje

NOMES_MESES = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)
DIAS_SEMANA = ("Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb")
PADRAO_MES = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


@dataclass(frozen=True, order=True, slots=True)
class Mes:
    ano: int
    mes: int

    @property
    def chave(self) -> str:
        return f"{self.ano:04d}-{self.mes:02d}"

    @property
    def titulo(self) -> str:
        return f"{NOMES_MESES[self.mes - 1]} {self.ano}"


@dataclass(frozen=True, slots=True)
class DiaCalendario:
    data: date
    pertence_ao_mes: bool
    hoje: bool
    passado: bool

    @property
    def numero(self) -> int:
        return self.data.day


def mes_da_data(data: date) -> Mes:
    return Mes(ano=data.year, mes=data.month)


def adicionar_meses(mes: Mes, quantidade: int) -> Mes:
    indice = mes.ano * 12 + (mes.mes - 1) + quantidade
    ano, indice_mes = divmod(indice, 12)
    return Mes(ano=ano, mes=indice_mes + 1)


def normalizar_mes(
    valor: str | None,
    data_hoje: date | None = None,
) -> tuple[Mes, bool]:
    """Retorna mês válido e se o valor informado estava dentro dos limites."""
    hoje = data_hoje or data_de_hoje()
    atual = mes_da_data(hoje)
    limite = adicionar_meses(atual, 12)

    if valor is None:
        return atual, True

    correspondencia = PADRAO_MES.fullmatch(valor)
    if correspondencia is None:
        return atual, False

    ano, mes = (int(parte) for parte in correspondencia.groups())
    if ano < 1:
        return atual, False
    solicitado = Mes(ano=ano, mes=mes)
    if solicitado > limite:
        return limite, False
    return solicitado, True


def ultimo_dia_do_mes(mes: Mes) -> date:
    proximo = adicionar_meses(mes, 1)
    return date(proximo.ano, proximo.mes, 1) - timedelta(days=1)


def dentro_da_janela_editavel(
    data: date,
    data_hoje: date | None = None,
) -> bool:
    hoje = data_hoje or data_de_hoje()
    limite = ultimo_dia_do_mes(adicionar_meses(mes_da_data(hoje), 12))
    return hoje <= data <= limite


def montar_grade(
    mes: Mes,
    data_hoje: date | None = None,
) -> list[list[DiaCalendario]]:
    """Monta semanas completas de domingo a sábado para o mês solicitado."""
    hoje = data_hoje or data_de_hoje()
    primeiro = date(mes.ano, mes.mes, 1)
    ultimo = ultimo_dia_do_mes(mes)

    deslocamento_inicio = (primeiro.weekday() + 1) % 7
    inicio_grade = primeiro - timedelta(days=deslocamento_inicio)
    indice_fim = (ultimo.weekday() + 1) % 7
    fim_grade = ultimo + timedelta(days=6 - indice_fim)

    dias: list[DiaCalendario] = []
    atual = inicio_grade
    while atual <= fim_grade:
        dias.append(
            DiaCalendario(
                data=atual,
                pertence_ao_mes=atual.month == mes.mes and atual.year == mes.ano,
                hoje=atual == hoje,
                passado=atual < hoje,
            )
        )
        atual += timedelta(days=1)

    return [dias[indice : indice + 7] for indice in range(0, len(dias), 7)]
