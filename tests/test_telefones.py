import pytest

from app.telefones import normalizar_telefone


@pytest.mark.parametrize(
    "entrada",
    [
        "(31) 99999-9999",
        "31 99999-9999",
        "31999999999",
    ],
)
def test_normaliza_telefone_br(entrada):
    resultado = normalizar_telefone(entrada)

    assert resultado == "31999999999"
    assert resultado.isascii()
    assert resultado.isdigit()
    assert len(resultado) == 11


@pytest.mark.parametrize(
    "entrada",
    [
        "31 9999-9999",
        "31 99999-999",
        "+55 31 99999-9999",
        "3A 99999-9999",
        "(31) 99999/9999",
        "",
    ],
)
def test_rejeita_telefone_invalido(entrada):
    with pytest.raises(ValueError, match="telefone"):
        normalizar_telefone(entrada)


def test_rejeita_valor_que_nao_seja_texto():
    with pytest.raises(ValueError, match="telefone"):
        normalizar_telefone(31999999999)  # type: ignore[arg-type]
