from __future__ import annotations
from typing import TYPE_CHECKING
from pydantic import BaseModel

from models import db_models

if TYPE_CHECKING:
    from models import core_models


class Transaction(BaseModel):
    sender: str
    receiver: str
    amount: float
    timestamp: float
    block_id: int | None = None

    def to_orm(self) -> db_models.Transaction:
        return db_models.Transaction(
            sender=self.sender,
            receiver=self.receiver,
            amount=self.amount,
            timestamp=self.timestamp,
            block_id=self.block_id
        )


class SignedTransaction(BaseModel):
    """Обёртка: транзакция + данные для валидации."""
    transaction: Transaction
    signature: str
    # public_key is now optional as it is not always needed
    public_key: str | None = None


class BlockHeader(BaseModel):
    previous_hash: str
    merkle_root: str
    timestamp: float
    nonce: int
    difficulty: int

    @classmethod
    def from_core(cls, block_header: "core_models.BlockHeader") -> "BlockHeader":
        return cls(
            previous_hash=block_header.previous_hash,
            merkle_root=block_header.merkle_root,
            timestamp=block_header.timestamp,
            nonce=block_header.nonce,
            difficulty=block_header.difficulty
        )


class Block(BaseModel):
    index: int
    transactions: list[Transaction]
    merkle_root: str
    header: BlockHeader
    hash: str

    def to_orm(self) -> db_models.Block:
        return db_models.Block(
            index=self.index,
            previous_hash=self.header.previous_hash,
            merkle_root=self.merkle_root,
            timestamp=self.header.timestamp,
            nonce=self.header.nonce,
            difficulty=self.header.difficulty,
            hash=self.hash,
        )

    @classmethod
    def from_core_block(cls, block: "core_models.Block") -> "Block":
        """Converts a core Block to an API Block."""
        api_transactions = [
            Transaction(
                sender=tx.sender,
                receiver=tx.receiver,
                amount=tx.amount,
                timestamp=tx.timestamp,
                block_id=block.index
            )
            for tx in block.transactions
        ]
        api_header = BlockHeader.from_core(block.header)
        return cls(
            index=block.index,
            transactions=api_transactions,
            merkle_root=block.merkle_root,
            header=api_header,
            hash=block.hash
        )
