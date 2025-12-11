# services/transaction_validator.py

from dataclasses import dataclass
from typing import Optional

from db.blockchain_dao import BlockchainDAO
from models.api_models import SignedTransaction
from infrastructure.utils import verify_signature, verify_sender_owns_address


@dataclass
class ValidationResult:
    is_valid: bool
    error: Optional[str] = None


class TransactionValidator:
    """Сервис для валидации подписанных транзакций."""

    SYSTEM_ADDRESS = "0" * 40

    def __init__(self, dao: BlockchainDAO, pending_transactions: list = None):
        self.dao = dao
        self.pending_transactions = pending_transactions or []

    def validate(self, signed_tx: SignedTransaction) -> ValidationResult:
        """Полная валидация подписанной транзакции."""
        tx = signed_tx.transaction

        # 1. Проверка адресов
        if not tx.sender:
            return ValidationResult(False, "Sender address is required")

        if not tx.receiver:
            return ValidationResult(False, "Receiver address is required")

        # 2. Проверка суммы
        if tx.amount <= 0:
            return ValidationResult(False, "Amount must be positive")

        # 3. Системные транзакции не проверяем
        if tx.sender == self.SYSTEM_ADDRESS:
            return ValidationResult(True)

        # 4. Проверка подписи
        signature_result = self._validate_signature(signed_tx)
        if not signature_result.is_valid:
            return signature_result

        # 5. Проверка баланса
        balance_result = self._validate_balance(tx)
        if not balance_result.is_valid:
            return balance_result

        return ValidationResult(True)

    def _validate_signature(self, signed_tx: SignedTransaction) -> ValidationResult:
        """Проверяет подпись."""
        tx = signed_tx.transaction

        # Публичный ключ должен соответствовать адресу
        if not verify_sender_owns_address(signed_tx.public_key, tx.sender):
            return ValidationResult(False, "Public key does not match sender address")

        # Подпись должна быть валидной
        is_valid = verify_signature(
            public_key_hex=signed_tx.public_key,
            signature_hex=signed_tx.signature,
            transaction_data=tx.to_dict()
        )

        if not is_valid:
            return ValidationResult(False, "Invalid signature")

        return ValidationResult(True)

    def _validate_balance(self, tx) -> ValidationResult:
        """Проверяет баланс отправителя."""
        confirmed = self._get_confirmed_balance(tx.sender)
        pending = self._get_pending_outgoing(tx.sender)
        available = confirmed - pending

        if available < tx.amount:
            return ValidationResult(
                False,
                f"Insufficient funds. Available: {available}, Required: {tx.amount}"
            )

        return ValidationResult(True)

    def _get_confirmed_balance(self, address: str) -> float:
        """Баланс из блокчейна."""
        blocks = self.dao.get_all_blocks()
        balance = 0.0

        for block in blocks:
            transactions = self.dao.get_transactions_by_block(block.id)
            for tx in transactions:
                if tx.receiver == address:
                    balance += tx.amount
                if tx.sender == address:
                    balance -= tx.amount

        return balance

    def _get_pending_outgoing(self, address: str) -> float:
        """Исходящие в pending пуле."""
        total = 0.0
        for tx in self.pending_transactions:
            sender = tx.sender if hasattr(tx, 'sender') else tx.get('sender')
            amount = tx.amount if hasattr(tx, 'amount') else tx.get('amount')
            if sender == address:
                total += amount
        return total
