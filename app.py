from http import HTTPStatus

import uvicorn
from fastapi import FastAPI, HTTPException

from core import db_session
from models.api_models import Block as APIBlock
from models.db_models import Block as ORMBlock, Transaction as ORMTransaction

app = FastAPI()

@app.post("/block", status_code=HTTPStatus.OK)
def create_block(block: APIBlock):
        try:
            with db_session.create_session() as session:

                orm_block = ORMBlock(
                    index=block.index,
                    previous_hash=block.header.previous_hash if block.header else None,
                    merkle_root=block.header.merkle_root if block.header else None,
                    timestamp=block.header.timestamp if block.header else None,
                    nonce=block.header.nonce if block.header else None,
                    difficulty=block.header.difficulty if block.header else None,
                    hash=block.hash
                )
                if block.transactions:
                    for tx in block.transactions:
                        orm_tx = ORMTransaction(
                            sender=tx.sender,
                            receiver=tx.receiver,
                            amount=tx.amount,
                            timestamp=tx.timestamp,
                            block=orm_block
                        )
                        session.add(orm_tx)

                session.add(orm_block)
                session.commit()

        except Exception as e:
            return HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))
        return HTTPStatus.OK




if __name__ == "__main__":
    db_session.global_init("db/block.sqlite")

    uvicorn.run(app, host="0.0.0.0", port=8000)
