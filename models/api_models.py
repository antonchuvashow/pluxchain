from pydantic import BaseModel

from models import core_models, db_models


class Transaction(BaseModel):
    sender: str
    receiver: str
    amount: float
    timestamp: float
    block_id: int

    @classmethod
    def from_class(cls, transaction: core_models.Transaction) -> "Transaction":
        return Transaction(sender=transaction.sender, receiver=transaction.receiver,
                           amount=transaction.amount, timestamp=transaction.timestamp)

    def to_orm(self) -> db_models.Transaction:
        return db_models.Transaction(sender=self.sender, receiver=self.receiver,)


class BlockHeader(BaseModel):
    previous_hash: str | None = None
    block_id: str | None = None
    block_number: str | None = None
    merkle_root: str | None = None
    timestamp: float | None = None
    nonce: int | None = None
    difficulty: int | None = None

    @classmethod
    def from_class(cls, block_header: core_models.BlockHeader) -> "BlockHeader":
        return BlockHeader(previous_hash=block_header.previous_hash, merkle_root=block_header.merkle_root,
                           timestamp=block_header.timestamp, nonce=block_header.nonce,
                           difficulty=block_header.difficulty)


class Block(BaseModel):
    index: int | None = None
    transactions: list[Transaction] | None = None
    merkle_root: str | None = None
    header: BlockHeader | None = None
    hash: str | None = None

    def to_orm(self) -> db_models.Block:
        return db_models.Block(index=self.index, previous_hash=self.header.previous_hash,
                               merkle_root=self.merkle_root, timestamp=self.header.timestamp,
                               nonce=self.header.nonce, difficulty=self.header.difficulty,
                               hash=self.hash,
                               )
