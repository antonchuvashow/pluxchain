import os
import sys
import time
import pytest
from fastapi.testclient import TestClient

# This line ensures that the root of the project is in the Python path.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Use a dedicated test database file
TEST_DB_PATH = "db/test_blockchain.sqlite"
os.environ["DATABASE_URL"] = TEST_DB_PATH

# Import the app after setting the environment variable
from app import app, MINING_REWARD
from infrastructure.utils import generate_keys, get_address_from_public_key, sign_transaction
from services.transaction_validator import TransactionValidator


@pytest.fixture(scope="module")
def client():
    """
    A pytest fixture to set up a TestClient.
    The client will use the database specified by the DATABASE_URL environment variable.
    It also handles the cleanup of the test database file.
    """
    with TestClient(app) as c:
        yield c
    
    # --- Test Teardown ---
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)



def test_full_workflow(client: TestClient):
    """
    **Workflow for Client Developers:**

    A "client" is a user's wallet application (e.g., a web or mobile app). The blockchain node
    (this server) NEVER handles private keys. The client is responsible for all cryptographic
    operations that require secrecy.

    1.  **Key Management (Client-Side):**
        - The user's wallet generates a private/public key pair (`generate_keys()`).
        - The private key is stored securely on the user's device and MUST NEVER be sent to the server.
        - The public key is used to derive the user's public blockchain address (`get_address_from_public_key()`).

    2.  **Transaction Signing (Client-Side):**
        - The wallet creates the raw transaction data (sender, receiver, amount, etc.).
        - It then uses the user's PRIVATE key to sign this data, creating a unique signature (`sign_transaction()`).

    3.  **Broadcasting to the Node (Client -> Server):**
        - The wallet sends a `SignedTransaction` object to the node's `/transactions` endpoint.
        - This object contains the public transaction data, the signature, and the user's PUBLIC key.

    4.  **Node Validation (Server-Side):**
        - The node receives the `SignedTransaction`. It uses the public key to verify that the signature
          is authentic and that the sender's address matches the public key. It has everything it
          needs for verification without ever seeing the private key.

    This end-to-end test simulates the entire blockchain workflow, including mining rewards.
    """

    # 1. Generate keys and addresses for participants
    alice_private, alice_public = generate_keys()
    bob_private, bob_public = generate_keys()
    miner_address = get_address_from_public_key(generate_keys()[1]) # A separate address for the miner
    charlie_address = get_address_from_public_key(generate_keys()[1])

    alice_address = get_address_from_public_key(alice_public)
    bob_address = get_address_from_public_key(bob_public)

    # 2. Fund Alice's account from the system faucet
    faucet_tx = {
        "transaction": {"sender": TransactionValidator.SYSTEM_ADDRESS, "receiver": alice_address, "amount": 100.0, "timestamp": time.time()},
        "signature": "dummy_signature", "public_key": "dummy_public_key"
    }
    response = client.post("/transactions", json=faucet_tx)
    assert response.status_code == 201, response.text

    # 3. Mine a block to confirm Alice's funds. The reward goes to the miner.
    mine_request_1 = {"miner_address": miner_address}
    response = client.post("/blocks/mine", json=mine_request_1)
    assert response.status_code == 201, response.text
    # The block should contain the faucet transaction + the reward transaction
    assert response.json()["block"]["transactions_count"] == 2

    # 4. Verify initial balances
    # Alice has her funds from the faucet
    response = client.get(f"/balance/{alice_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == 100.0
    # The miner has their first reward
    response = client.get(f"/balance/{miner_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == MINING_REWARD

    # 5. Create and sign the first real transaction (Alice to Bob)
    tx1_data = {"sender": alice_address, "receiver": bob_address, "amount": 10.0, "timestamp": time.time()}
    tx1_signature = sign_transaction(alice_private, tx1_data)
    signed_tx1 = {"transaction": tx1_data, "signature": tx1_signature, "public_key": alice_public}
    response = client.post("/transactions", json=signed_tx1)
    assert response.status_code == 201, response.text

    # 6. Create and sign the second real transaction (Bob to Charlie)
    tx2_data = {"sender": bob_address, "receiver": charlie_address, "amount": 5.0, "timestamp": time.time()}
    tx2_signature = sign_transaction(bob_private, tx2_data)
    signed_tx2 = {"transaction": tx2_data, "signature": tx2_signature, "public_key": bob_public}
    response = client.post("/transactions", json=signed_tx2)
    assert response.status_code == 201, response.text

    # 7. Mine the main block with the two transactions. Reward goes to the miner again.
    mine_request_2 = {"miner_address": miner_address}
    response = client.post("/blocks/mine", json=mine_request_2)
    assert response.status_code == 201, response.text
    # This block should contain Alice->Bob, Bob->Charlie, and the reward transaction
    assert response.json()["block"]["transactions_count"] == 3

    # 8. Check final balances
    response = client.get(f"/balance/{alice_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == 90.0  # 100 - 10

    response = client.get(f"/balance/{bob_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == 5.0  # Received 10, sent 5

    response = client.get(f"/balance/{charlie_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == 5.0
    
    # The miner has now received two rewards
    response = client.get(f"/balance/{miner_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == MINING_REWARD * 2


def test_mine_on_empty_block(client: TestClient):
    """
    This test demonstrates how a miner can create coins "from empty air" by mining a block
    even when there are no pending user transactions. This is THE PRIMARY WAY new currency
    is introduced into the blockchain.
    """

    # 1. Define a new miner for this test
    miner_address = get_address_from_public_key(generate_keys()[1])
    
    # 2. Verify there are no pending transactions from users
    response = client.get("/transactions/pending")
    assert response.status_code == 200
    assert response.json()["count"] == 0

    # 3. The miner starts "bruteforcing" a new block.
    # By calling `/blocks/mine`, we are telling the node to start the Proof of Work process.
    # The node will repeatedly hash the block header with a different "nonce" until it finds
    # a hash that meets the network's difficulty target (e.g., starts with '0000').
    # This computationally expensive work is the "bruteforce".
    print(f"Miner ({miner_address[:10]}...) started mining on an empty block...")
    mine_request = {"miner_address": miner_address}
    response = client.post("/blocks/mine", json=mine_request)
    
    # 4. The node found a valid hash and created a block.
    assert response.status_code == 201, response.text
    mined_block = response.json()
    print(f"Block mined successfully! Hash: {mined_block['block']['hash']}")

    # 5. Verify the block contains ONLY the miner's reward.
    # This is the "coinbase" transaction.
    assert mined_block["block"]["transactions_count"] == 1
    assert mined_block["block"]["miner_reward"] == MINING_REWARD

    # 6. Verify the new coins were created and sent to the miner's address.
    response = client.get(f"/balance/{miner_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == MINING_REWARD
    print(f"Miner's balance is now {response.json()['balance']}. Coins were created from empty air!")
