from __future__ import annotations
import hashlib
import time
import json
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse
import httpx

from config import settings

# Use Uvicorn's logger
logger = logging.getLogger("uvicorn.error")

if TYPE_CHECKING:
    from db.blockchain_dao import BlockchainDAO
    from models import api_models


class Transaction:
    def __init__(self, sender: str, receiver: str, amount: float, timestamp: float = None) -> None:
        self.sender: str = sender
        self.receiver: str = receiver
        self.amount: float = amount
        self.timestamp: float = timestamp or time.time()
    def to_dict(self) -> dict:
        return {"sender": self.sender, "receiver": self.receiver, "amount": self.amount, "timestamp": self.timestamp}
    def calculate_hash(self) -> str:
        tx_string = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(tx_string.encode()).hexdigest()

class BlockHeader:
    def __init__(self, previous_hash: str, merkle_root: str, timestamp: float = None, nonce: int = 0, difficulty: int = settings.difficulty) -> None:
        self.previous_hash: str = previous_hash
        self.merkle_root: str = merkle_root
        self.timestamp: float = timestamp or time.time()
        self.nonce: int = nonce
        self.difficulty: int = difficulty
    def calculate_hash(self) -> str:
        header_string = f"{self.previous_hash}{self.merkle_root}{self.timestamp}{self.nonce}{self.difficulty}"
        return hashlib.sha256(header_string.encode()).hexdigest()

class Block:
    def __init__(self, index: int, transactions: list[Transaction], previous_hash: str, difficulty: int = settings.difficulty) -> None:
        self.index: int = index
        self.transactions: list[Transaction] = transactions
        self.merkle_root: str = self.compute_merkle_root()
        self.header: BlockHeader = BlockHeader(previous_hash, self.merkle_root, difficulty=difficulty)
        self.hash: str = self.mine_block()
    def compute_merkle_root(self) -> str:
        tx_hashes = [tx.calculate_hash() for tx in self.transactions]
        if not tx_hashes: return hashlib.sha256().hexdigest()
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0: tx_hashes.append(tx_hashes[-1])
            tx_hashes = [hashlib.sha256((tx_hashes[i] + tx_hashes[i + 1]).encode()).hexdigest() for i in range(0, len(tx_hashes), 2)]
        return tx_hashes[0]
    def mine_block(self) -> str:
        while True:
            hash_val = self.header.calculate_hash()
            if hash_val.startswith("0" * self.header.difficulty): return hash_val
            self.header.nonce += 1
    def is_valid(self) -> bool:
        return (self.hash == self.header.calculate_hash() and self.hash.startswith("0" * self.header.difficulty))

def create_genesis_block() -> Block:
    genesis_tx = Transaction(settings.system_address, "0" * 40, 1000.0)
    return Block(index=1, transactions=[genesis_tx], previous_hash="0" * 64, difficulty=settings.difficulty)


class Blockchain(object):
    def __init__(self, dao: "BlockchainDAO"):
        from models.api_models import Block as APIBlock
        self.chain: list[APIBlock] = []
        self.current_transactions: list[Transaction] = []
        self.dao = dao
        self.nodes = set()

        db_blocks = self.dao.get_all_blocks()
        if not db_blocks:
            logger.warning("No blocks found in DB, creating genesis block...")
            genesis = create_genesis_block()
            api_block = APIBlock.from_core_block(genesis)
            self.new_block(api_block)
            self.chain.append(api_block)
        else:
            logger.info(f"Loading {len(db_blocks)} blocks from DB...")
            self.chain = [APIBlock.from_db_model(b) for b in db_blocks]

    def register_node(self, address: str):
        parsed_url = urlparse(address)
        netloc = parsed_url.netloc or parsed_url.path
        if netloc:
            if netloc not in self.nodes:
                self.nodes.add(netloc)
                logger.info(f"Registered new node: {netloc}")
            else:
                logger.debug(f"Node already registered: {netloc}")
        else:
            logger.error(f"Invalid URL provided for node registration: {address}")
            raise ValueError('Invalid URL')

    def valid_chain(self, chain: list[dict]) -> bool:
        if not chain:
            return False

        for i in range(len(chain)):
            block = chain[i]
            
            # 1. Verify that the block's difficulty matches the node's own setting.
            # This prevents accepting chains with a lower (cheaper) proof-of-work.
            if block['header']['difficulty'] != settings.difficulty:
                logger.warning(
                    f"Chain validation failed: Invalid difficulty at index {block['index']}. "
                    f"Block has difficulty {block['header']['difficulty']} but node requires {settings.difficulty}."
                )
                return False

            # 2. Re-calculate the block's hash and verify its integrity and PoW.
            header_string = f"{block['header']['previous_hash']}{block['merkle_root']}{block['header']['timestamp']}{block['header']['nonce']}{block['header']['difficulty']}"
            calculated_hash = hashlib.sha256(header_string.encode()).hexdigest()

            if calculated_hash != block['hash']:
                logger.warning(f"Chain validation failed: Block hash mismatch at index {block['index']}.")
                return False

            if not block['hash'].startswith('0' * settings.difficulty):
                logger.warning(f"Chain validation failed: PoW is invalid at index {block['index']} for difficulty {settings.difficulty}.")
                return False

            # 3. For all blocks after the genesis block, verify the previous_hash link.
            if i > 0:
                last_block = chain[i - 1]
                if block['header']['previous_hash'] != last_block['hash']:
                    logger.warning(f"Chain validation failed: Previous hash mismatch at index {block['index']}.")
                    return False
        
        logger.info("Full chain validation successful.")
        return True

    def valid_chain_headers(self, headers: list[dict]) -> bool:
        """
        Validates a list of block headers.
        Headers are expected to be ordered from oldest to newest (index ascending).
        """
        if not headers:
            return False

        # Validate genesis block header first
        genesis_header = headers[0]
        # Reconstruct the header to calculate its hash
        header_string = f"{genesis_header['previous_hash']}{genesis_header['merkle_root']}{genesis_header['timestamp']}{genesis_header['nonce']}{genesis_header['difficulty']}"
        calculated_hash = hashlib.sha256(header_string.encode()).hexdigest()

        if calculated_hash != genesis_header['hash']:
            logger.warning("Header validation failed: Genesis block header hash mismatch.")
            return False
        if not genesis_header['hash'].startswith('0' * genesis_header['difficulty']):
            logger.warning("Header validation failed: Genesis block header PoW is invalid.")
            return False

        for i in range(1, len(headers)):
            header = headers[i]
            prev_header = headers[i-1]

            # 1. Check that the previous_hash in the current header matches the hash of the previous header.
            if header['previous_hash'] != prev_header['hash']:
                logger.warning(f"Header validation failed: Previous hash mismatch at index {header['index']}.")
                return False

            # 2. Check the Proof of Work for each header.
            # Reconstruct the header to calculate its hash
            header_string = f"{header['previous_hash']}{header['merkle_root']}{header['timestamp']}{header['nonce']}{header['difficulty']}"
            calculated_hash = hashlib.sha256(header_string.encode()).hexdigest()

            if calculated_hash != header['hash']:
                logger.warning(f"Header validation failed: Header hash mismatch at index {header['index']}.")
                return False

            if not header['hash'].startswith('0' * header['difficulty']):
                logger.warning(f"Header validation failed: PoW is invalid at index {header['index']}.")
                return False
        
        logger.info("Chain headers validation successful.")
        return True


    async def resolve_conflicts(self) -> bool:
        from models.api_models import Block as APIBlock
        neighbours = self.nodes
        new_chain = None
        # Use get_total_blocks_count which exists and is used elsewhere
        max_length = self.dao.get_total_blocks_count()
        authoritative_node_url = None
        
        logger.info(f"Starting conflict resolution. Current chain length: {max_length}")
        logger.info(f"Known neighbours: {list(neighbours)}")
        logger.info(f"My address: {settings.my_network_address}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Iterate through all known nodes to find the longest valid chain
            for node in neighbours:
                if node == settings.my_network_address:
                    logger.debug(f"Skipping self ({node}).")
                    continue

                logger.info(f"--> Querying node: {node}")
                try:
                    # 1. Get the length of the chain on the neighbor node
                    # We can get this from the /chain endpoint without fetching all blocks
                    response = await client.get(f'http://{node}/chain?page_size=1')
                    if response.status_code != 200:
                        logger.warning(f"Node {node} responded with status {response.status_code} for chain length.")
                        continue
                    
                    remote_length = response.json()['length']
                    logger.info(f"Node {node} reports chain length: {remote_length}. Current max known length: {max_length}")

                    # 2. If the neighbor's chain is longer, it's a candidate.
                    if remote_length > max_length:
                        logger.info(f"Found a candidate for the longest chain at {node} (length {remote_length}). Downloading for verification...")
                        
                        # 3. Download the full chain from the candidate node
                        full_chain_response = await client.get(f'http://{node}/chain?page_size={remote_length}')
                        if full_chain_response.status_code != 200:
                            logger.warning(f"Failed to download full chain from {node}. Status: {full_chain_response.status_code}")
                            continue

                        chain_data = full_chain_response.json()['chain']
                        
                        # 4. Validate the downloaded chain
                        if self.valid_chain(chain_data):
                            logger.info(f"Successfully validated chain from {node}. It is now the authoritative chain.")
                            # This is now the longest valid chain we've found so far
                            max_length = remote_length
                            new_chain = chain_data
                            authoritative_node_url = node
                        else:
                            logger.warning(f"Downloaded chain from {node} is INVALID. Ignoring.")
                    else:
                        logger.info(f"Chain from {node} is not longer than the current longest ({max_length}).")

                except (httpx.RequestError, json.JSONDecodeError) as e:
                    logger.error(f"Could not connect to or parse data from node {node}: {e}")

        # 5. After checking all neighbors, if we found a longer valid chain, replace ours.
        if new_chain and authoritative_node_url:
            logger.info(f"Replacing local chain with the longer valid chain from {authoritative_node_url}.")
            self.dao.replace_chain(new_chain)
            self.current_transactions = []  # Clear mempool
            self.chain = [APIBlock.from_db_model(b) for b in self.dao.get_all_blocks()] # Reload from DB
            return True

        logger.info("Current chain is authoritative. No replacement needed.")
        return False

    def new_block(self, block: "api_models.Block") -> "api_models.Block":
        self.dao.add_block(block.to_orm(), [transaction.to_orm() for transaction in block.transactions])
        return block

    def new_transaction(self, transaction: Transaction):
        self.current_transactions.append(transaction)
        return self.last_block.index + 1

    @property
    def last_block(self) -> "api_models.Block":
        last_block_db = self.dao.get_last_block()
        from models.api_models import Block as APIBlock
        return APIBlock.from_db_model(last_block_db)
