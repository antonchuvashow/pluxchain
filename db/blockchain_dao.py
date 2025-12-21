from sqlalchemy.orm import joinedload
from db.db_session import create_session
from models.db_models import Block, Transaction


class BlockchainDAO:
    def add_block(self, block_orm: Block, transaction_orms: list[Transaction]) -> Block:
        """
        Сохраняет блок с транзакциями в БД.
        """
        with create_session() as session:
            session.add(block_orm)
            session.flush()
            for tx in transaction_orms:
                tx.block_id = block_orm.id
                session.add(tx)
            session.commit()
            session.refresh(block_orm)
            return block_orm

    def get_block(self, block_id: int) -> Block | None:
        """
        Получить блок по ID.
        """
        with create_session() as session:
            return (
                session.query(Block)
                .options(joinedload(Block.transactions))
                .filter(Block.id == block_id)
                .first()
            )

    def get_all_blocks(self, limit: int = None, offset: int = 0) -> list[Block]:
        """
        Получить все блоки, с возможностью пагинации.
        """
        with create_session() as session:
            query = (
                session.query(Block)
                .options(joinedload(Block.transactions))
                .order_by(Block.index.asc())
            )
            if limit:
                query = query.limit(limit).offset(offset)
            return query.all()

    def get_all_block_headers(self, limit: int = None, offset: int = 0) -> list[dict]:
        """
        Получить только заголовки всех блоков, с возможностью пагинации.
        """
        with create_session() as session:
            query = (
                session.query(
                    Block.index,
                    Block.previous_hash,
                    Block.merkle_root,
                    Block.timestamp,
                    Block.nonce,
                    Block.difficulty,
                    Block.hash
                )
                .order_by(Block.index.asc())
            )
            if limit:
                query = query.limit(limit).offset(offset)
            
            headers_data = []
            for block_header_tuple in query.all():
                headers_data.append({
                    "index": block_header_tuple.index,
                    "previous_hash": block_header_tuple.previous_hash,
                    "merkle_root": block_header_tuple.merkle_root,
                    "timestamp": block_header_tuple.timestamp,
                    "nonce": block_header_tuple.nonce,
                    "difficulty": block_header_tuple.difficulty,
                    "hash": block_header_tuple.hash,
                })
            return headers_data

    def get_total_blocks_count(self) -> int:
        """Возвращает общее количество блоков."""
        with create_session() as session:
            return session.query(Block).count()

    def get_last_block(self) -> Block | None:
        """
        Получить последний добавленный блок.
        """
        with create_session() as session:
            return (
                session.query(Block)
                .options(joinedload(Block.transactions))
                .order_by(Block.index.desc())
                .first()
            )

    def get_transactions_by_block(self, block_id: int) -> list[Transaction]:
        """
        Получить все транзакции блока.
        """
        with create_session() as session:
            return session.query(Transaction).filter(Transaction.block_id == block_id).all()

    def get_all_transactions(self, limit: int = None, offset: int = 0) -> list[Transaction]:
        """
        Получить все транзакции из всех блоков, с возможностью пагинации.
        """
        with create_session() as session:
            query = session.query(Transaction).order_by(Transaction.id.desc())
            if limit:
                query = query.limit(limit).offset(offset)
            return query.all()

    def get_total_transactions_count(self) -> int:
        """Возвращает общее количество транзакций."""
        with create_session() as session:
            return session.query(Transaction).count()

    def get_transaction(self, tx_id: int) -> Transaction | None:
        """
        Получить транзакцию по ID.
        """
        with create_session() as session:
            return session.query(Transaction).filter(Transaction.id == tx_id).first()

    def get_chain_length(self) -> int:
        """
        Возвращает количество блоков в цепи.
        """
        with create_session() as session:
            return session.query(Block).count()

    def replace_chain(self, chain_data: list[dict]):
        """
        Заменяет существующую цепочку блоков на новую.
        """
        with create_session() as session:
            # 1. Удаляем старые данные
            session.query(Transaction).delete()
            session.query(Block).delete()

            # 2. Добавляем новые блоки и транзакции
            for block_data in chain_data:
                # Создаем ORM-объект блока
                block_orm = Block(
                    index=block_data['index'],
                    previous_hash=block_data['header']['previous_hash'],
                    merkle_root=block_data['merkle_root'],
                    timestamp=block_data['header']['timestamp'],
                    nonce=block_data['header']['nonce'],
                    difficulty=block_data['header']['difficulty'],
                    hash=block_data['hash']
                )
                session.add(block_orm)
                session.flush()  # Получаем ID для блока

                # Создаем ORM-объекты транзакций
                for tx_data in block_data['transactions']:
                    tx_orm = Transaction(
                        sender=tx_data['sender'],
                        receiver=tx_data['receiver'],
                        amount=tx_data['amount'],
                        timestamp=tx_data['timestamp'],
                        block_id=block_orm.id
                    )
                    session.add(tx_orm)
            
            session.commit()
