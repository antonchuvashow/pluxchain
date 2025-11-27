from db.db_session import create_session
from models.db_models import Block, Transaction


class BlockchainDAO:
    def add_block(self, block_orm: Block, transaction_orms: list[Transaction]) -> Block:
        """
        Сохраняет блок с транзакциями в БД.
        """
        with create_session() as session:
            # сначала сохранить блок
            session.add(block_orm)
            session.flush()

            # привязать транзакции к блоку
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

    def get_all_blocks(self) -> list[Block]:
        """
        Получить все блоки.
        """
        with create_session() as session:
            return session.query(Block).order_by(Block.id.asc()).all()

    def get_last_block(self) -> Block | None:
        """
        Получить последний добавленный блок.
        """
        with create_session() as session:
            return session.query(Block).order_by(Block.index.desc()).first()

    def add_transaction(self, tx_orm: Transaction) -> Transaction:
        """
        Добавить одну транзакцию в БД.
        """
        with create_session() as session:
            session.add(tx_orm)
            session.commit()
            session.refresh(tx_orm)
            return tx_orm

    def get_transactions_by_block(self, block_id: int) -> list[Transaction]:
        """
        Получить все транзакции блока.
        """
        with create_session() as session:
            return session.query(Transaction).filter(Transaction.block_id == block_id).all()

    def get_transaction(self, tx_id: int) -> Transaction | None:
        """
        Получить транзакцию по ID.
        """
        with create_session() as session:
            return session.query(Transaction).filter(Transaction.id == tx_id).first()
