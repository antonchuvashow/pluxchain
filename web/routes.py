from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime

# Import the global app objects to access their data
import app as main_app

# Create a router for the web panel
router = APIRouter()

# Point to the templates directory
templates = Jinja2Templates(directory="web/templates")

# Add a custom filter to the Jinja2 environment to format timestamps
templates.env.filters["datetime"] = lambda ts: datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


@router.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """
    Serves the main dashboard page, showing node status and latest blocks.
    """
    if not main_app.blockchain or not main_app.dao:
        raise HTTPException(status_code=503, detail="Application not initialized")

    # Get data directly from your application's state
    chain_length = len(main_app.blockchain.chain)
    pending_tx_count = len(main_app.blockchain.current_transactions)
    
    # Get the last 10 blocks from the DAO
    all_blocks = main_app.dao.get_all_blocks()
    
    # Add transaction counts to each block for display
    display_blocks = []
    for block in all_blocks:
        block.transactions_count = len(main_app.dao.get_transactions_by_block(block.id))
        display_blocks.append(block)

    latest_blocks = sorted(display_blocks, key=lambda b: b.index, reverse=True)[:10]

    # Prepare the context to pass to the template
    context = {
        "request": request,
        "chain_length": chain_length,
        "pending_tx_count": pending_tx_count,
        "latest_blocks": latest_blocks,
    }
    
    return templates.TemplateResponse("dashboard.html", context)

@router.get("/block/{block_index}", response_class=HTMLResponse)
async def get_block_details(request: Request, block_index: int):
    """
    Serves a detail page for a specific block.
    """
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
