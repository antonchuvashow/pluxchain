from __future__ import annotations
from typing import TYPE_CHECKING
from pydantic import BaseModel, ConfigDict

from models import db_models
from models import core_models # Added for runtime use

if TYPE_CHECKING:
    pass # core_models is now imported above


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
    
    model_config = ConfigDict(from_attributes=True) # Re-added this line


class SignedTransaction(BaseModel):
    """Обёртка: транзакция + данные для валидации."""
    transaction: Transaction
    signature: str
    public_key: str | None = None


class BlockHeader(BaseModel):
    previous_hash: str
    merkle_root: str
    timestamp: float
    nonce: int
    difficulty: int
    hash: str

    @classmethod
    def from_core(cls, block_header: "core_models.BlockHeader") -> "BlockHeader":
        return cls(
            previous_hash=block_header.previous_hash,
            merkle_root=block_header.merkle_root,
            timestamp=block_header.timestamp,
            nonce=block_header.nonce,
            difficulty=block_header.difficulty,
            hash=block_header.calculate_hash()
        )
    
    # Removed: model_config = ConfigDict(from_attributes=True) - Keep this removed for BlockHeader


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

    @classmethod
    def from_db_model(cls, block_orm: db_models.Block) -> "Block": # Renamed from from_orm
        """Converts a db_models.Block to an API Block."""
        # Create a core_models.BlockHeader instance to calculate the header's hash
        core_header_instance = core_models.BlockHeader(
            previous_hash=block_orm.previous_hash,
            merkle_root=block_orm.merkle_root,
            timestamp=block_orm.timestamp,
            nonce=block_orm.nonce,
            difficulty=block_orm.difficulty
        )
        header_hash = core_header_instance.calculate_hash()

        # Create the APIBlockHeader explicitly
        api_header = BlockHeader(
            previous_hash=block_orm.previous_hash,
            merkle_root=block_orm.merkle_root,
            timestamp=block_orm.timestamp,
            nonce=block_orm.nonce,
            difficulty=block_orm.difficulty,
            hash=header_hash
        )

        # Convert DB transactions to API transactions using Transaction.from_orm
        api_transactions = [Transaction.from_orm(tx) for tx in block_orm.transactions]

        return cls(
            index=block_orm.index,
            transactions=api_transactions,
            merkle_root=block_orm.merkle_root,
            header=api_header,
            hash=block_orm.hash, # This is the block's hash, from db_models.Block
        )

    # Removed: model_config = ConfigDict(from_attributes=True) - Keep this removed for Block
