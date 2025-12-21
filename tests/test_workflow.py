import os
import sys
import time
import pytest
from fastapi.testclient import TestClient

# This line ensures that the root of the project is in the Python path.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Use a dedicated test database file and set the environment variable
TEST_DB_PATH = "db/test_blockchain.sqlite"
os.environ["DATABASE_URL"] = TEST_DB_PATH

# Import the app and settings after setting the environment variable
from app import app
from config import settings
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
    
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


def test_full_workflow(client: TestClient):
    """
    This end-to-end test simulates the entire blockchain workflow, including mining rewards.
    """
    # 1. Generate keys and addresses for participants
    alice_private, alice_public = generate_keys()
    bob_private, bob_public = generate_keys()
    miner_address = get_address_from_public_key(generate_keys()[1])
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
    assert response.json()["block"]["transactions_count"] == 2

    # 4. Verify initial balances
    response = client.get(f"/balance/{alice_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == 100.0
    response = client.get(f"/balance/{miner_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == settings.mining_reward

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
    assert response.json()["block"]["transactions_count"] == 3

    # 8. Check final balances
    response = client.get(f"/balance/{alice_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == 90.0
    response = client.get(f"/balance/{bob_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == 5.0
    response = client.get(f"/balance/{charlie_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == 5.0
    response = client.get(f"/balance/{miner_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == settings.mining_reward * 2


def test_mine_on_empty_block(client: TestClient):
    """
    This test demonstrates how a miner can create coins "from empty air" by mining a block
    even when there are no pending user transactions.
    """
    miner_address = get_address_from_public_key(generate_keys()[1])
    
    response = client.get("/transactions/pending")
    assert response.status_code == 200
    assert response.json()["count"] == 0

    mine_request = {"miner_address": miner_address}
    response = client.post("/blocks/mine", json=mine_request)
    
    assert response.status_code == 201, response.text
    mined_block = response.json()
    assert mined_block["block"]["transactions_count"] == 1
    assert mined_block["block"]["miner_reward"] == settings.mining_reward

    response = client.get(f"/balance/{miner_address}")
    assert response.status_code == 200, response.text
    assert response.json()["balance"] == settings.mining_reward
