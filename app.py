from http import HTTPStatus

import uvicorn
from fastapi import FastAPI, HTTPException

from db import db_session
from db.blockchain_dao import BlockchainDAO
from models.api_models import Block as APIBlock, Transaction as APITransaction, SignedTransaction, \
    BlockHeader as APIBlockHeader
from models.core_models import Blockchain, Transaction, Block
from services.transaction_validator import TransactionValidator

app = FastAPI()
dao = BlockchainDAO()
blockchain = Blockchain(dao)


# ============== ТРАНЗАКЦИИ ==============


@app.post("/transactions", status_code=HTTPStatus.CREATED)
def receive_transaction(signed_tx: SignedTransaction):
    """
    Принимает подписанную транзакцию.
    """

    # Валидация
    validator = TransactionValidator(
        dao=dao,
        pending_transactions=blockchain.current_transactions
    )

    result = validator.validate(signed_tx)

    if not result.is_valid:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=result.error)

    # Добавляем чистую транзакцию в пул
    tx = Transaction(
        sender=signed_tx.transaction.sender,
        receiver=signed_tx.transaction.receiver,
        amount=signed_tx.transaction.amount,
        timestamp=signed_tx.transaction.timestamp
    )
    blockchain.current_transactions.append(tx)

    return {
        "message": "Transaction accepted",
        "tx_hash": tx.calculate_hash(),
        "pending_count": len(blockchain.current_transactions)
    }


@app.get("/transactions/pending")
def get_pending_transactions():
    """
    Возвращает список необработанных транзакций.
    """
    return {
        "count": len(blockchain.current_transactions),
        "transactions": [tx.to_dict() for tx in blockchain.current_transactions]
    }


# ============== МАЙНИНГ ==============

@app.post("/blocks/mine", status_code=HTTPStatus.CREATED)
def mine_block():
    """
    Берёт транзакции из пула, формирует и майнит новый блок.
    """
    # 1. Проверяем есть ли транзакции
    if not blockchain.current_transactions:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="No pending transactions to mine"
        )

    # 2. Получаем данные последнего блока
    last_block = dao.get_last_block()

    if last_block:
        previous_hash = last_block.hash
        new_index = last_block.index + 1
    else:
        previous_hash = "0" * 64
        new_index = 1

    # 3. Создаём и майним блок
    new_block = Block(
        index=new_index,
        transactions=blockchain.current_transactions.copy(),
        previous_hash=previous_hash,
        difficulty=4
    )

    # 4. Конвертируем транзакции в API модель
    api_transactions = [
        APITransaction(
            sender=tx.sender,
            receiver=tx.receiver,
            amount=tx.amount,
            timestamp=tx.timestamp,
            block_id=new_block.index
        )
        for tx in new_block.transactions
    ]

    # 5. Формируем API блок
    api_block = APIBlock(
        index=new_block.index,
        transactions=api_transactions,
        merkle_root=new_block.merkle_root,
        header=APIBlockHeader(
            previous_hash=new_block.header.previous_hash,
            merkle_root=new_block.merkle_root,
            timestamp=new_block.header.timestamp,
            nonce=new_block.header.nonce,
            difficulty=new_block.header.difficulty
        ),
        hash=new_block.hash
    )

    # 6. Сохраняем в БД
    blockchain.new_block(api_block)

    # 7. Очищаем пул
    mined_count = len(blockchain.current_transactions)
    blockchain.current_transactions = []

    return {
        "message": "Block mined successfully",
        "block": {
            "index": new_block.index,
            "hash": new_block.hash,
            "previous_hash": new_block.header.previous_hash,
            "nonce": new_block.header.nonce,
            "difficulty": new_block.header.difficulty,
            "transactions_count": mined_count,
            "merkle_root": new_block.merkle_root,
            "timestamp": new_block.header.timestamp
        }
    }


# ============== ЦЕПОЧКА ==============

@app.get("/chain")
def get_chain():
    """
    Возвращает всю цепочку блоков.
    """
    blocks = dao.get_all_blocks()
    return {
        "length": len(blocks),
        "chain": [
            {
                "index": b.index,
                "hash": b.hash,
                "previous_hash": b.previous_hash,
                "timestamp": b.timestamp,
                "transactions_count": len(dao.get_transactions_by_block(b.id))
            }
            for b in blocks
        ]
    }


@app.get("/blocks")
def get_blocks():
    """
    Список всех блоков.
    """
    return dao.get_all_blocks()


@app.get("/blocks/{block_id}")
def get_block(block_id: int):
    """
    Получить конкретный блок по ID.
    """
    block = dao.get_block(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    transactions = dao.get_transactions_by_block(block_id)
    return {
        "block": block,
        "transactions": transactions
    }


# ============== БАЛАНС ==============

@app.get("/balance/{address}")
def get_balance(address: str):
    """
    Вычисляет баланс адреса по всем транзакциям в блокчейне.
    """
    blocks = dao.get_all_blocks()
    balance = 0.0

    for block in blocks:
        transactions = dao.get_transactions_by_block(block.id)
        for tx in transactions:
            if tx.receiver == address:
                balance += tx.amount
            if tx.sender == address:
                balance -= tx.amount

    return {
        "address": address,
        "balance": balance
    }


@app.post("/block", status_code=HTTPStatus.OK)
def create_block(block: APIBlock):
    try:
        blockchain.new_block(block)
    except Exception as e:
        return HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))
    return HTTPStatus.OK


if __name__ == "__main__":
    db_session.global_init("db/block.sqlite")

    uvicorn.run(app, host="0.0.0.0", port=8000)
