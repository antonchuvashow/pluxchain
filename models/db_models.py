from sqlalchemy import Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import TYPE_CHECKING

from db.db_session import SqlAlchemyBase

if TYPE_CHECKING:
    from models.api_models import BlockHeader


class Transaction(SqlAlchemyBase):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    block_id: Mapped[int] = mapped_column(ForeignKey("blocks.id"))

    sender: Mapped[str] = mapped_column(String)
    receiver: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[float] = mapped_column(Float)

    block: Mapped["Block"] = relationship("Block", back_populates="transactions")


class Block(SqlAlchemyBase):
    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index: Mapped[int] = mapped_column()

    previous_hash: Mapped[str] = mapped_column(String)
    merkle_root: Mapped[str] = mapped_column(String)
    timestamp: Mapped[float] = mapped_column(Float)
    nonce: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[int] = mapped_column(Integer)

    hash: Mapped[str] = mapped_column(String, unique=True)

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="block",
        cascade="all, delete-orphan"
    )

    @property
    def header(self) -> "BlockHeader":
        from models.api_models import BlockHeader
        return BlockHeader(
            previous_hash=self.previous_hash,
            merkle_root=self.merkle_root,
            timestamp=self.timestamp,
            nonce=self.nonce,
            difficulty=self.difficulty,
        )
