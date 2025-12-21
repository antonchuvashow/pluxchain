from contextlib import asynccontextmanager
from http import HTTPStatus
import uvicorn
import os
import httpx
import logging
from fastapi import FastAPI, HTTPException, Body, Query
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles

from config import settings
from db import db_session
from db.blockchain_dao import BlockchainDAO
from models.api_models import Block as APIBlock, SignedTransaction, BlockHeader as APIBlockHeader, \
    Transaction as APITransaction
from models.core_models import Blockchain, Transaction, Block
from services.transaction_validator import TransactionValidator
from web.routes import router as web_router
from web.connection_manager import manager

logger = logging.getLogger("uvicorn.error")

# --- Global State ---
dao: BlockchainDAO | None = None
blockchain: Blockchain | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global dao, blockchain
    print("Initializing application...")
    db_path = os.getenv("DATABASE_URL", "db/block.sqlite")
    print(f"Using database at: {db_path}")
    db_session.global_init(db_path)
    dao = BlockchainDAO()
    blockchain = Blockchain(dao)
    logger.info("Initialization completed.")

    # --- Регистрация узла ---
    blockchain.register_node(settings.my_address)

    if settings.seed_nodes:
        async with httpx.AsyncClient() as client:
            for node_url in settings.seed_nodes:
                try:
                    await client.post(f"http://{node_url}/nodes/register", json={"address": settings.my_address})
                    response = await client.get(f"http://{node_url}/nodes")
                    if response.status_code == 200:
                        nodes = response.json().get("nodes", [])
                        for node in nodes:
                            blockchain.register_node(node)
                except httpx.RequestError as e:
                    logger.error(f"Couldn't connect to seed-node {node_url}: {e}")

    yield
    print("Shutting down.")


app = FastAPI(
    lifespan=lifespan,
    title="Pluxchain API",
    description="""
### API для взаимодействия с учебным блокчейном Pluxchain.

Этот интерфейс позволяет:
*   **Управлять транзакциями**: создавать, подписывать и отправлять монеты.
*   **Майнить блоки**: участвовать в консенсусе Proof-of-Work.
*   **Синхронизировать узлы**: регистрировать новые ноды и разрешать конфликты цепочек.
*   **Просматривать данные**: получать информацию о блоках, заголовках и балансах.
    """,
    version="1.0.0",
    contact={
        "name": "Pluxchain Dev Team",
    },
)

# --- Подключение статики и веб-роутера ---
app.mount("/static", StaticFiles(directory="web/static"), name="static")
app.include_router(web_router, prefix="/panel", tags=["Веб-панель"])


# --- API Models for Requests ---
class MineRequest(BaseModel):
    miner_address: str = Field(..., description="Адрес кошелька майнера, куда будет начислена награда")


class NodeRegisterRequest(BaseModel):
    address: str = Field(..., example="127.0.0.1:8001", description="Адрес узла (хост:порт)")


# ============== NETWORK ENDPOINTS ==============

@app.post("/nodes/register", status_code=HTTPStatus.CREATED, tags=["Сеть"], summary="Регистрация нового узла")
def register_node(payload: NodeRegisterRequest):
    """
    **Регистрирует новый узел в сети.**

    Этот эндпоинт используется другими узлами (пирами), чтобы сообщить о своем существовании.
    После регистрации текущий узел сможет опрашивать новый узел для синхронизации блокчейна.

    - **address**: Адрес узла в формате `host:port`.
    """
    node_address = payload.address
    if not node_address:
        raise HTTPException(status_code=400, detail="Incorrect node address")

    blockchain.register_node(node_address)

    return {
        "message": "New node successfully registered",
        "total_nodes": list(blockchain.nodes),
    }


@app.get("/nodes", tags=["Сеть"], summary="Список известных узлов")
def get_nodes():
    """
    **Возвращает список всех известных узлов (пиров) в сети.**

    Используется для discovery (обнаружения) сети новыми участниками.
    """
    return {"nodes": list(blockchain.nodes)}


@app.post("/nodes/resolve", status_code=HTTPStatus.OK, tags=["Сеть"], summary="Консенсус (разрешение конфликтов)")
async def resolve_nodes():
    """
    **Запускает алгоритм консенсуса.**

    Узел опрашивает всех известных соседей, скачивает их цепочки блоков и проверяет их валидность.
    Если найдена цепочка длиннее и валиднее текущей, локальная цепочка заменяется на скачанную.

    *Возвращает статус операции: была ли заменена цепочка.*
    """
    replaced = await blockchain.resolve_conflicts()
    if replaced:
        message = "Our chain was replaced"
    else:
        message = "Our chain is authoritative"

    return {"message": message}


# ============== API ENDPOINTS ==============

@app.post("/transactions", status_code=HTTPStatus.CREATED, tags=["Транзакции"], summary="Отправка новой транзакции")
async def receive_transaction(signed_tx: SignedTransaction):
    """
    **Принимает новую транзакцию для добавления в блокчейн.**

    Процесс обработки:
    1. Проверяется **цифровая подпись** (Signature) отправителя.
    2. Проверяется **баланс** отправителя (достаточно ли средств).
    3. Если проверка пройдена, транзакция добавляется в **Mempool** (список ожидающих).
    4. Транзакция рассылается другим узлам через WebSocket.

    Требует переданную структуру `SignedTransaction`, содержащую данные транзакции и подпись.
    """
    validator = TransactionValidator(dao=dao, pending_transactions=blockchain.current_transactions)
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
    await manager.broadcast({"type": "new_pending_tx", "data": tx.to_dict()})
    logger.info(f"Transaction accepted: {tx.calculate_hash()}")

    return {"message": "Transaction accepted", "tx_hash": tx.calculate_hash()}


@app.get("/transactions/pending", tags=["Транзакции"], summary="Просмотр Mempool (очереди транзакций)")
def get_pending_transactions():
    """
    **Возвращает список всех транзакций, ожидающих включения в блок.**

    Эти транзакции находятся в оперативной памяти узла и еще не записаны в базу данных (блокчейн) окончательно.
    Они будут включены в следующий блок при майнинге.
    """
    return {
        "count": len(blockchain.current_transactions),
        "transactions": [tx.to_dict() for tx in blockchain.current_transactions]
    }


@app.post("/blocks/mine", status_code=HTTPStatus.CREATED, tags=["Блокчейн"], summary="Майнинг нового блока")
async def mine_block(request: MineRequest):
    """
    **Запускает процесс майнинга (Proof-of-Work).**

    Действия:
    1. Собирает все транзакции из Mempool.
    2. Добавляет **Coinbase-транзакцию** (награду майнеру) первым пунктом.
    3. Подбирает `nonce`, чтобы хеш блока удовлетворял сложности сети.
    4. Сохраняет блок в БД и оповещает сеть.

    - **miner_address**: Адрес кошелька, на который придет награда.
    """
    reward_tx = Transaction(sender=settings.system_address, receiver=request.miner_address,
                            amount=settings.mining_reward)
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

    blockchain.current_transactions = []  # Очистка пула после майнинга
    await manager.broadcast({"type": "new_block_mined", "data": {"index": new_api_block.index}})
    logger.info(f"New block #{new_api_block.index} mined successfully.")

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


@app.get("/chain", tags=["Блокчейн"], summary="Получить полную цепочку блоков")
def get_chain(
        page: int = Query(1, ge=1, description="Номер страницы"),
        page_size: int = Query(10, ge=1, le=100, description="Количество блоков на странице")
):
    """
    **Возвращает список блоков блокчейна с пагинацией.**

    Каждый блок содержит полную информацию:
    *   Заголовок (хеш, прошлый хеш, nonce, timestamp)
    *   Список всех транзакций внутри блока.
    """
    total_blocks = dao.get_total_blocks_count()
    offset = (page - 1) * page_size
    blocks_from_db = dao.get_all_blocks(limit=page_size, offset=offset)

    chain_data = []
    for block_db in blocks_from_db:
        header = APIBlockHeader(
            previous_hash=block_db.previous_hash,
            merkle_root=block_db.merkle_root,
            timestamp=block_db.timestamp,
            nonce=block_db.nonce,
            difficulty=block_db.difficulty,
            hash=block_db.hash
        )
        transactions = [APITransaction.from_orm(tx) for tx in block_db.transactions]

        api_block = APIBlock(
            index=block_db.index,
            transactions=transactions,
            merkle_root=block_db.merkle_root,
            header=header,
            hash=block_db.hash,
        )
        chain_data.append(api_block.model_dump())

    return {
        "length": total_blocks,
        "chain": chain_data,
        "page": page,
        "page_size": page_size
    }


@app.get("/chain/headers", tags=["Блокчейн"], summary="Получить только заголовки блоков")
def get_chain_headers(
        page: int = Query(1, ge=1, description="Номер страницы"),
        page_size: int = Query(10, ge=1, le=100, description="Количество заголовков на странице")
):
    """
    **Возвращает облегченную версию цепочки (только заголовки).**

    Не содержит транзакций. Используется для быстрой синхронизации ("Light Client")
    и проверки целостности цепочки (хешей) без загрузки больших объемов данных.
    """
    total_blocks = dao.get_total_blocks_count()
    offset = (page - 1) * page_size
    headers_from_db = dao.get_all_block_headers(limit=page_size, offset=offset)

    api_headers = []
    for header_data in headers_from_db:
        api_headers.append(APIBlockHeader(
            previous_hash=header_data['previous_hash'],
            merkle_root=header_data['merkle_root'],
            timestamp=header_data['timestamp'],
            nonce=header_data['nonce'],
            difficulty=header_data['difficulty'],
            hash=header_data['hash']
        ).model_dump())

    return {
        "length": total_blocks,
        "headers": api_headers,
        "page": page,
        "page_size": page_size
    }


@app.get("/blocks/{block_id}", tags=["Блокчейн"], summary="Получить блок по ID")
def get_block(block_id: int):
    """
    **Возвращает детальную информацию о конкретном блоке.**

    Поиск производится по `index` (высоте) блока.
    Возвращает как метаданные блока, так и список включенных в него транзакций.
    """
    block = dao.get_block(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Блок не найден")
    transactions = dao.get_transactions_by_block(block.id)
    return {"block": block, "transactions": transactions}


@app.get("/balance/{address}", tags=["Кошелек"], summary="Узнать баланс адреса")
def get_balance(address: str):
    """
    **Рассчитывает текущий баланс для указанного адреса.**

    Алгоритм:
    Проходит по всей истории транзакций в блокчейне:
    *   Прибавляет сумму, если адрес является получателем (`receiver`).
    *   Вычитает сумму, если адрес является отправителем (`sender`).

    *Примечание: В реальных системах используется UTXO или кэширование состояния (World State), данный метод может быть медленным при большой истории.*
    """
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