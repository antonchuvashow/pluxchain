import json
import os
from domain.models import Transaction, Block


def save_block(block, filepath: str):
    """
    Сохраняет блок в JSON-файл.
    Если файл уже существует, добавляет новый блок в цепочку.
    """
    block_data = {
        "index": block.index,
        "transactions": [tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in block.transactions],
        "previous_hash": block.header.previous_hash,
        "merkle_root": block.merkle_root,
        "timestamp": block.header.timestamp,
        "nonce": block.header.nonce,
        "difficulty": block.header.difficulty,
        "hash": block.hash
    }

    blockchain = []
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                blockchain = json.load(f)
            except json.JSONDecodeError:
                blockchain = []

    blockchain.append(block_data)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(blockchain, f, indent=4, ensure_ascii=False)


def load_block(filepath: str, index: int):
    """
    Загружает блок из JSON-файла по индексу.
    Возвращает объект класса Block.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Файл {filepath} не найден")

    with open(filepath, "r", encoding="utf-8") as f:
        blockchain = json.load(f)

    if index < 0 or index >= len(blockchain):
        raise IndexError("Неверный индекс блока")

    data = blockchain[index]

    # Восстановление транзакций
    transactions = [Transaction(tx["sender"], tx["receiver"], tx["amount"], tx["timestamp"])
                    for tx in data["transactions"]]

    # Создание блока
    block = Block(
        index=data["index"],
        transactions=transactions,
        previous_hash=data["previous_hash"],
        difficulty=data["difficulty"]
    )

    # Восстановление параметров хедера и хэша
    block.header.timestamp = data["timestamp"]
    block.header.nonce = data["nonce"]
    block.hash = data["hash"]

    return block


def create_genesis_block():
    """
    Генерирует первый (генезис) блок блокчейна.
    previous_hash фиксирован, так как предыдущего блока не существует.
    """
    genesis_tx = Transaction("system", "network", 0)
    genesis_block = Block(index=0, transactions=[genesis_tx], previous_hash="0" * 64)
    return genesis_block