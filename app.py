from http import HTTPStatus

import uvicorn
from fastapi import FastAPI, HTTPException

from db import db_session
from db.blockchain_dao import BlockchainDAO
from models.api_models import Block as APIBlock
from models.core_models import Blockchain

app = FastAPI()
dao = BlockchainDAO()
blockchain = Blockchain(dao)

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
