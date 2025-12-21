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
            return session.query(Block).filter(Block.id == block_id).first()

    def get_all_blocks(self, limit: int = None, offset: int = 0) -> list[Block]:
        """
        Получить все блоки, с возможностью пагинации.
        """
        with create_session() as session:
            query = session.query(Block).order_by(Block.index.desc())
            if limit:
                query = query.limit(limit).offset(offset)
            return query.all()

    def get_total_blocks_count(self) -> int:
        """Возвращает общее количество блоков."""
        with create_session() as session:
            return session.query(Block).count()

    def get_last_block(self) -> Block | None:
        """
        Получить последний добавленный блок.
        """
        with create_session() as session:
            return session.query(Block).order_by(Block.index.desc()).first()

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
