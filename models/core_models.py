from __future__ import annotations
import hashlib
import time
import json
from typing import TYPE_CHECKING

from config import settings

if TYPE_CHECKING:
    from db.blockchain_dao import BlockchainDAO
    from models import api_models


class Transaction:
    """
    Класс, представляющий отдельную транзакцию в блокчейне.
    Каждая транзакция содержит информацию об отправителе, получателе, сумме и метке времени.
    """

    def __init__(self, sender: str, receiver: str, amount: float, timestamp: float = None) -> None:
        self.sender: str = sender
        self.receiver: str = receiver
        self.amount: float = amount
        self.timestamp: float = timestamp or time.time()

    def to_dict(self) -> dict:
        """Возвращает транзакцию в виде словаря для сериализации."""
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "timestamp": self.timestamp
        }

    def calculate_hash(self) -> str:
        """Возвращает хэш SHA-256 от данных транзакции."""
        tx_string = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(tx_string.encode()).hexdigest()


class BlockHeader:
    """
    Заголовок блока, содержащий хэш предыдущего блока, корень Меркла, временную метку,
    сложность и nonce, используемый для майнинга.
    """

    def __init__(self, previous_hash: str, merkle_root: str,
                 timestamp: float = None, nonce: int = 0, difficulty: int = settings.difficulty) -> None:
        self.previous_hash: str = previous_hash
        self.merkle_root: str = merkle_root
        self.timestamp: float = timestamp or time.time()
        self.nonce: int = nonce
        self.difficulty: int = difficulty

    def calculate_hash(self) -> str:
        """Возвращает хэш заголовка блока."""
        header_string = f"{self.previous_hash}{self.merkle_root}{self.timestamp}{self.nonce}{self.difficulty}"
        return hashlib.sha256(header_string.encode()).hexdigest()


class Block:
    """
    Класс блока, содержащего список транзакций, заголовок и метод майнинга.
    """

    def __init__(self, index: int, transactions: list[Transaction], previous_hash: str, difficulty: int = settings.difficulty) -> None:
        self.index: int = index
        self.transactions: list[Transaction] = transactions
        self.merkle_root: str = self.compute_merkle_root()
        self.header: BlockHeader = BlockHeader(previous_hash, self.merkle_root, difficulty=difficulty)
        self.hash: str = self.mine_block()

    def compute_merkle_root(self) -> str:
        """
        Вычисляет корень для всех транзакций в блоке.
        """
        tx_hashes = [tx.calculate_hash() for tx in self.transactions]
        if not tx_hashes:
            return hashlib.sha256().hexdigest()
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
            tx_hashes = [
                hashlib.sha256((tx_hashes[i] + tx_hashes[i + 1]).encode()).hexdigest()
                for i in range(0, len(tx_hashes), 2)
            ]
        return tx_hashes[0]

    def mine_block(self) -> str:
        """
        Выполняет процесс майнинга блока.
        """
        while True:
            hash_val = self.header.calculate_hash()
            if hash_val.startswith("0" * self.header.difficulty):
                return hash_val
            self.header.nonce += 1

    def is_valid(self) -> bool:
        """
        Проверяет корректность блока.
        """
        return (self.hash == self.header.calculate_hash() and
                self.hash.startswith("0" * self.header.difficulty))


def create_genesis_block() -> Block:
    """
    Генерирует первый (генезис) блок блокчейна.
    """
    genesis_tx = Transaction("system", "0" * 40, 1000.0)
    genesis_block = Block(index=1, transactions=[genesis_tx], previous_hash="0" * 64, difficulty=settings.difficulty)
    return genesis_block


class Blockchain(object):
    def __init__(self, dao: "BlockchainDAO"):
        from models.api_models import Block as APIBlock
        self.chain: list[APIBlock] = []
        self.current_transactions: list[Transaction] = []
        self.dao = dao

        genesis = create_genesis_block()
        api_block = APIBlock.from_core_block(genesis)
        self.new_block(api_block)

    def new_block(self, block: "api_models.Block") -> "api_models.Block":
        """Adds a new block to the chain."""
        self.dao.add_block(block.to_orm(), [transaction.to_orm() for transaction in block.transactions])
        self.chain.append(block)
        return block

    def new_transaction(self, transaction: Transaction):
        # Вносит новую транзакцию в список транзакций
        self.current_transactions.append(transaction)
        # Return the index of the block that will hold this transaction
        return self.last_block.index + 1

    @property
    def last_block(self) -> "api_models.Block":
        # Возвращает последний блок в цепочке
        return self.chain[-1]
