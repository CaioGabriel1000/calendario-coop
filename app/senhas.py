"""Hash e verificação de senhas usando Argon2id."""

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher(type=Type.ID)


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def verificar_senha(senha_hash: str, senha: str) -> bool:
    try:
        return _hasher.verify(senha_hash, senha)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False
