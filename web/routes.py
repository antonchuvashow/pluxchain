from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import math

# Import the global app objects and settings
import app as main_app
from config import settings

# Create a router for the web panel
router = APIRouter()

# Point to the templates directory
templates = Jinja2Templates(directory="web/templates")

# Add a custom filter to the Jinja2 environment to format timestamps
templates.env.filters["datetime"] = lambda ts: datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

ITEMS_PER_PAGE = 20

@router.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """
    Serves the main dashboard page, showing status, pending transactions, and latest blocks.
    """
    if not main_app.blockchain or not main_app.dao:
        raise HTTPException(status_code=503, detail="Application not initialized")

    # Get data directly from your application's state
    chain_length = main_app.dao.get_total_blocks_count()
    pending_txs = main_app.blockchain.current_transactions
    total_tx_count = main_app.dao.get_total_transactions_count()
    
    all_blocks = main_app.dao.get_all_blocks(limit=10) # Get latest 10 for dashboard
    
    display_blocks = []
    for block in all_blocks:
        block.transactions_count = len(main_app.dao.get_transactions_by_block(block.id))
        display_blocks.append(block)

    context = {
        "request": request,
        "chain_length": chain_length,
        "pending_txs": pending_txs,
        "total_tx_count": total_tx_count,
        "latest_blocks": display_blocks,
    }
    
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/blocks", response_class=HTMLResponse)
async def get_all_blocks_paginated(request: Request, page: int = Query(1, ge=1)):
    if not main_app.dao:
        raise HTTPException(status_code=503, detail="Application not initialized")

    total_count = main_app.dao.get_total_blocks_count()
    total_pages = math.ceil(total_count / ITEMS_PER_PAGE)
    offset = (page - 1) * ITEMS_PER_PAGE

    blocks = main_app.dao.get_all_blocks(limit=ITEMS_PER_PAGE, offset=offset)
    for block in blocks:
        block.transactions_count = len(main_app.dao.get_transactions_by_block(block.id))

    context = {
        "request": request,
        "blocks": blocks,
        "total_count": total_count,
        "page": page,
        "total_pages": total_pages,
    }
    return templates.TemplateResponse("all_blocks.html", context)


@router.get("/transactions", response_class=HTMLResponse)
async def get_all_transactions_paginated(request: Request, page: int = Query(1, ge=1)):
    if not main_app.dao:
        raise HTTPException(status_code=503, detail="Application not initialized")

    total_count = main_app.dao.get_total_transactions_count()
    total_pages = math.ceil(total_count / ITEMS_PER_PAGE)
    offset = (page - 1) * ITEMS_PER_PAGE

    transactions = main_app.dao.get_all_transactions(limit=ITEMS_PER_PAGE, offset=offset)

    context = {
        "request": request,
        "transactions": transactions,
        "total_count": total_count,
        "page": page,
        "total_pages": total_pages,
    }
    return templates.TemplateResponse("all_transactions.html", context)


@router.get("/block/{block_index}", response_class=HTMLResponse)
async def get_block_details(request: Request, block_index: int):
    if not main_app.dao:
        raise HTTPException(status_code=503, detail="Application not initialized")

    block = main_app.dao.get_block(block_index)
    if not block:
        raise HTTPException(status_code=404, detail=f"Block with index {block_index} not found.")

    transactions = main_app.dao.get_transactions_by_block(block.id)

    context = {
        "request": request,
        "block": block,
        "transactions": transactions,
    }
    return templates.TemplateResponse("block_details.html", context)
