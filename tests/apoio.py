"""Dados auxiliares usados pelos testes."""

from hashlib import sha256


def telefone_de_teste(chave: str) -> str:
    numero = int.from_bytes(sha256(chave.encode()).digest()[:4], "big") % 1_000_000_000
    return f"31{numero:09d}"
