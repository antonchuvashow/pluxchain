import hashlib
import json
import os
from typing import Tuple

from ecdsa import VerifyingKey, SECP256k1, BadSignatureError, SigningKey

from models.core_models import Transaction, Block


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
    genesis_tx = Transaction("system", "0" * 64, 1000.0)
    genesis_block = Block(index=0, transactions=[genesis_tx], previous_hash="0" * 64)
    return genesis_block


# ============== КРИПТОГРАФИЯ ==============

def generate_keys() -> Tuple[str, str]:
    """
    Генерирует пару ключей (приватный, публичный).
    Возвращает в hex формате.
    """
    private_key = SigningKey.generate(curve=SECP256k1)
    public_key = private_key.get_verifying_key()

    return (
        private_key.to_string().hex(),
        public_key.to_string().hex()
    )


def get_address_from_public_key(public_key_hex: str) -> str:
    """
    Генерирует адрес из публичного ключа.
    Адрес = первые 40 символов от SHA256(public_key).
    """
    return hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]


def sign_transaction(private_key_hex: str, transaction_data: dict) -> str:
    """
    Подписывает данные транзакции приватным ключом.
    Возвращает подпись в hex формате.
    """
    private_key = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)

    # Формируем строку для подписи (без signature и public_key)
    data_to_sign = {
        "sender": transaction_data["sender"],
        "receiver": transaction_data["receiver"],
        "amount": transaction_data["amount"],
        "timestamp": transaction_data["timestamp"]
    }
    message = json.dumps(data_to_sign, sort_keys=True).encode()
    message_hash = hashlib.sha256(message).digest()

    signature = private_key.sign(message_hash)
    return signature.hex()


def verify_signature(public_key_hex: str, signature_hex: str, transaction_data: dict) -> bool:
    """
    Проверяет подпись транзакции.
    Возвращает True если подпись валидна.
    """
    try:
        public_key = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
        signature = bytes.fromhex(signature_hex)

        data_to_verify = {
            "sender": transaction_data["sender"],
            "receiver": transaction_data["receiver"],
            "amount": transaction_data["amount"],
            "timestamp": transaction_data["timestamp"]
        }
        message = json.dumps(transaction_data, sort_keys=True).encode()
        message_hash = hashlib.sha256(message).digest()

        return public_key.verify(signature, message_hash)

    except (BadSignatureError, ValueError, Exception):
        return False


def verify_sender_owns_address(public_key_hex: str, sender_address: str) -> bool:
    """
    Проверяет, что публичный ключ соответствует адресу отправителя.
    """
    derived_address = get_address_from_public_key(public_key_hex)
    return derived_address == sender_address
