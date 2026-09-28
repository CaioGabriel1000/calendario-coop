"""Base declarativa e modelos do banco."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        UniqueConstraint("email", name="uq_usuarios_email"),
        Index("uq_usuarios_apelido_lower", func.lower(text("apelido")), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    apelido: Mapped[str] = mapped_column(String(12), nullable=False)
    senha_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    falhas_login: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
