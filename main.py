from models.core_models import Transaction, Block, create_genesis_block
from infrastructure.utils import save_block

main_block = create_genesis_block()
transactions = []
for i in range(5):
    transactions.append(Transaction(str(i), str(i + 1), float(i * 2 + 2)))

block = Block(1, transactions, main_block.hash)
save_block(main_block, "main_block.json")
save_block(block, "block.json")