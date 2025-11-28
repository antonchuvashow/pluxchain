import hashlib
import time
import json

from db.blockchain_dao import BlockchainDAO
from infrastructure.utils import create_genesis_block
from models.api_models import Block as APIBlock


class Transaction:
    """
    Класс, представляющий отдельную транзакцию в блокчейне.
    Каждая транзакция содержит информацию об отправителе, получателе, сумме и метке времени.
    """

    def __init__(self, sender: str, receiver: str, amount: float, timestamp: float = None) -> None:
        self.sender: str = sender                # Адрес или имя отправителя
        self.receiver: str = receiver            # Адрес или имя получателя
        self.amount: float = amount                # Сумма перевода
        self.timestamp: float = timestamp or time.time()  # Время создания транзакции

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
                 timestamp: float = None, nonce: int = 0, difficulty: int = 4) -> None:
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

    def __init__(self, index: int, transactions: list[Transaction], previous_hash: str, difficulty: int = 4) -> None:
        self.index: int = index                                     # Индекс блока в цепочке
        self.transactions: list[Transaction] = transactions                       # Список транзакций (объекты Transaction)
        self.merkle_root: str = self.compute_merkle_root()           # Корень Меркла для проверки целостности транзакций
        self.header: BlockHeader = BlockHeader(previous_hash, self.merkle_root, difficulty=difficulty)
        self.hash: str = self.mine_block()                           # Хэш найденного блока после майнинга

    def compute_merkle_root(self) -> str:
        """
        Вычисляет корень для всех транзакций в блоке.
        Используется для проверки целостности данных.
        """
        tx_hashes = [tx.calculate_hash() if isinstance(tx, Transaction)
                     else hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest()
                     for tx in self.transactions]
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
        Выполняет процесс майнинга блока перебирает nonce, пока не будет найден хэш,
        начинающийся с заданного количества нулей (в зависимости от сложности).
        """
        while True:
            hash_val = self.header.calculate_hash()
            if hash_val.startswith("0" * self.header.difficulty):
                return hash_val
            self.header.nonce += 1

    def is_valid(self) -> bool:
        """
        Проверяет корректность блока
        """
        return (self.hash == self.header.calculate_hash() and
                self.hash.startswith("0" * self.header.difficulty))


class Blockchain(object):
    def __init__(self, dao: BlockchainDAO):
        self.chain = []
        self.current_transactions = []
        self.dao = dao

        self.new_block(create_genesis_block())

    def new_block(self, block: APIBlock) -> APIBlock:
        # Создает новый блок и вносит его в цепь
        self.current_transactions = []
        self.dao.add_block(block.to_orm(), [transaction.to_orm() for transaction in block.transactions])
        self.chain.append(block)
        return block

    def new_transaction(self, transaction: Transaction):
        # Вносит новую транзакцию в список транзакций
        self.current_transactions.append(transaction)
        return self.last_block.index + 1

    @property
    def last_block(self) -> Block:
        # Возвращает последний блок в цепочке
        return self.chain[-1]

