# services/transaction_validator.py

from dataclasses import dataclass
from typing import Optional

from db.blockchain_dao import BlockchainDAO
from models.api_models import SignedTransaction, Transaction
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

        if not tx.sender or not tx.receiver:
            return ValidationResult(False, "Sender and receiver addresses are required")
        if tx.amount <= 0:
            return ValidationResult(False, "Amount must be positive")
        if tx.sender == self.SYSTEM_ADDRESS:
            return ValidationResult(True)

        signature_result = self._validate_signature(signed_tx)
        if not signature_result.is_valid:
            return signature_result

        balance_result = self._validate_balance(tx)
        if not balance_result.is_valid:
            return balance_result

        return ValidationResult(True)

    def _validate_signature(self, signed_tx: SignedTransaction) -> ValidationResult:
        """Проверяет подпись."""
        tx = signed_tx.transaction
        if not verify_sender_owns_address(signed_tx.public_key, tx.sender):
            return ValidationResult(False, "Public key does not match sender address")

        is_valid = verify_signature(
            public_key_hex=signed_tx.public_key,
            signature_hex=signed_tx.signature,
            transaction_data=tx.model_dump(exclude={'block_id'})
        )
        if not is_valid:
            return ValidationResult(False, "Invalid signature")

        return ValidationResult(True)

    def _validate_balance(self, tx: Transaction) -> ValidationResult:
        """Проверяет баланс отправителя, учитывая подтвержденные и ожидающие транзакции."""
        confirmed = self._get_confirmed_balance(tx.sender)
        pending_outgoing = self._get_pending_outgoing(tx.sender)
        pending_incoming = self._get_pending_incoming(tx.sender)
        
        available = confirmed + pending_incoming - pending_outgoing

        if available < tx.amount:
            return ValidationResult(
                False,
                f"Insufficient funds. Available: {available}, Required: {tx.amount}"
            )
        return ValidationResult(True)

    def _get_confirmed_balance(self, address: str) -> float:
        """Баланс из всех подтвержденных транзакций в блокчейне."""
        balance = 0.0
        all_transactions = self.dao.get_all_transactions()
        for tx in all_transactions:
            if tx.receiver == address:
                balance += tx.amount
            if tx.sender == address:
                balance -= tx.amount
        return balance

    def _get_pending_outgoing(self, address: str) -> float:
        """Сумма исходящих транзакций в пуле ожидания."""
        total = 0.0
        for pt in self.pending_transactions:
            sender = getattr(pt, 'sender', None)
            amount = getattr(pt, 'amount', 0)
            if sender == address:
                total += amount
        return total

    def _get_pending_incoming(self, address: str) -> float:
        """Сумма входящих транзакций в пуле ожидания."""
        total = 0.0
        for pt in self.pending_transactions:
            receiver = getattr(pt, 'receiver', None)
            amount = getattr(pt, 'amount', 0)
            if receiver == address:
                total += amount
        return total
