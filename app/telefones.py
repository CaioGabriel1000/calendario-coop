"""Validação e normalização de telefones brasileiros."""

import re


_MASCARA_TELEFONE = re.compile(r"[\s()-]")
_TELEFONE_NORMALIZADO = re.compile(r"[0-9]{11}")


def normalizar_telefone(telefone: str) -> str:
    """Remove máscara permitida e valida DDD (2) + telefone (9 dígitos)."""
    if not isinstance(telefone, str):
        raise ValueError("O telefone deve conter DDD e 9 dígitos.")

    normalizado = _MASCARA_TELEFONE.sub("", telefone)
    if _TELEFONE_NORMALIZADO.fullmatch(normalizado) is None:
        raise ValueError("O telefone deve conter DDD e 9 dígitos (11 números).")
    return normalizado
