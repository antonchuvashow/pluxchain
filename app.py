from contextlib import asynccontextmanager
from http import HTTPStatus
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import settings
from db import db_session
from db.blockchain_dao import BlockchainDAO
from models.api_models import Block as APIBlock, SignedTransaction
from models.core_models import Blockchain, Transaction, Block
from services.transaction_validator import TransactionValidator

# --- Global State ---
dao: BlockchainDAO | None = None
blockchain: Blockchain | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global dao, blockchain
    print("Initializing application...")
    print(f"Using database at: {settings.database_url}")
    db_session.global_init(settings.database_url)
    dao = BlockchainDAO()
    blockchain = Blockchain(dao)
    print("Initialization complete.")
    yield
    print("Shutting down.")


app = FastAPI(lifespan=lifespan)


# --- API Models for Requests ---
class MineRequest(BaseModel):
    miner_address: str


# ============== ТРАНЗАКЦИИ ==============

@app.post("/transactions", status_code=HTTPStatus.CREATED)
def receive_transaction(signed_tx: SignedTransaction):
    validator = TransactionValidator(
        dao=dao,
        pending_transactions=blockchain.current_transactions
    )
    result = validator.validate(signed_tx)
    if not result.is_valid:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=result.error)

    tx = Transaction(
        sender=signed_tx.transaction.sender,
        receiver=signed_tx.transaction.receiver,
        amount=signed_tx.transaction.amount,
        timestamp=signed_tx.transaction.timestamp
    )
    blockchain.current_transactions.append(tx)
    return {"message": "Transaction accepted", "tx_hash": tx.calculate_hash()}


@app.get("/transactions/pending")
def get_pending_transactions():
    return {
        "count": len(blockchain.current_transactions),
        "transactions": [tx.to_dict() for tx in blockchain.current_transactions]
    }


# ============== МАЙНИНГ ==============

@app.post("/blocks/mine", status_code=HTTPStatus.CREATED)
def mine_block(request: MineRequest):
    reward_tx = Transaction(
        sender=TransactionValidator.SYSTEM_ADDRESS,
        receiver=request.miner_address,
        amount=settings.mining_reward
    )

    transactions_for_block = blockchain.current_transactions.copy()
    transactions_for_block.insert(0, reward_tx)

    last_block_orm = dao.get_last_block()
    previous_hash = last_block_orm.hash if last_block_orm else "0" * 64
    new_index = (last_block_orm.index + 1) if last_block_orm else 1

    new_core_block = Block(
        index=new_index,
        transactions=transactions_for_block,
        previous_hash=previous_hash,
        difficulty=settings.difficulty
    )

    new_api_block = APIBlock.from_core_block(new_core_block)
    blockchain.new_block(new_api_block)
    blockchain.current_transactions = []

    return {
        "message": "Block mined successfully",
        "block": {
            "index": new_api_block.index,
            "hash": new_api_block.hash,
            "transactions_count": len(new_api_block.transactions),
            "miner_reward": settings.mining_reward,
            "miner_address": request.miner_address
        }
    }


# ============== ЦЕПОЧКА ==============

@app.get("/chain")
def get_chain():
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


@app.get("/blocks/{block_id}")
def get_block(block_id: int):
    block = dao.get_block(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    transactions = dao.get_transactions_by_block(block_id)
    return {"block": block, "transactions": transactions}


# ============== БАЛАНС ==============

@app.get("/balance/{address}")
def get_balance(address: str):
    balance = 0.0
    all_transactions = dao.get_all_transactions()
    for tx in all_transactions:
        if tx.receiver == address:
            balance += tx.amount
        if tx.sender == address:
            balance -= tx.amount
    return {"address": address, "balance": balance}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
