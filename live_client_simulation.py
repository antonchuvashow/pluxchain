import requests
import time
from infrastructure.utils import generate_keys, get_address_from_public_key, sign_transaction

# --- Configuration ---
BASE_URL = "http://127.0.0.1:8000"

def print_status(message, is_ok=True):
    """Helper function to print colored status messages."""
    OK_GREEN = '\033[92m'
    FAIL_RED = '\033[91m'
    ENDC = '\033[0m'
    color = OK_GREEN if is_ok else FAIL_RED
    print(f"{color} {message}{ENDC}")

def run_simulation():
    """
    Runs a full workflow simulation against a live PluxChain node.
    This script acts as a real external client.
    """
    try:
        # 1. Generate keys and addresses for participants
        miner_private, miner_public = generate_keys()
        alice_private, alice_public = generate_keys()
        bob_private, bob_public = generate_keys()

        miner_address = get_address_from_public_key(miner_public)
        alice_address = get_address_from_public_key(alice_public)
        bob_address = get_address_from_public_key(bob_public)
        
        print_status("Generated cryptographic identities for a Miner, Alice, and Bob.")
        print(f"  - Miner's Address: {miner_address}")
        print(f"  - Alice's Address: {alice_address}")
        print(f"  - Bob's Address:   {bob_address}")
        print("-" * 50)
        time.sleep(2)

        # 2. The Miner earns the first coins by mining an empty block
        print_status("Step 1: A miner starts work to earn the first coins in the ecosystem...")
        mine_request_1 = {"miner_address": miner_address}
        response = requests.post(f"{BASE_URL}/blocks/mine", json=mine_request_1)
        assert response.status_code == 201
        print_status(f"Block mined! The miner earned their first reward. Check the panel.")
        time.sleep(3)

        # 3. Verify the miner's initial balance
        response = requests.get(f"{BASE_URL}/balance/{miner_address}")
        miner_balance = response.json()["balance"]
        assert miner_balance > 0
        print_status(f"Verified Miner's balance is now {miner_balance} coins.")
        print("-" * 50)
        time.sleep(2)

        # 4. The Miner (who now has funds) sends money to Alice
        print_status("Step 2: The miner is sending 10.0 coins to Alice...")
        tx_data_to_alice = {"sender": miner_address, "receiver": alice_address, "amount": 10.0, "timestamp": time.time()}
        signature_to_alice = sign_transaction(miner_private, tx_data_to_alice)
        signed_tx_to_alice = {"transaction": tx_data_to_alice, "signature": signature_to_alice, "public_key": miner_public}
        
        response = requests.post(f"{BASE_URL}/transactions", json=signed_tx_to_alice)
        assert response.status_code == 201
        print_status("Transaction from Miner to Alice accepted. Check the panel for the pending transaction.")
        time.sleep(5)

        # 5. The Miner mines the block with the transaction to Alice
        print_status("Step 3: Mining the block to confirm Alice's funds...")
        mine_request_2 = {"miner_address": miner_address}
        response = requests.post(f"{BASE_URL}/blocks/mine", json=mine_request_2)
        assert response.status_code == 201
        print_status("Block mined! Alice's funds are now confirmed.")
        print("-" * 50)
        time.sleep(3)

        # 6. Alice sends money to Bob
        print_status("Step 4: Alice is sending 5.0 coins to Bob...")
        tx_data_to_bob = {"sender": alice_address, "receiver": bob_address, "amount": 5.0, "timestamp": time.time()}
        signature_to_bob = sign_transaction(alice_private, tx_data_to_bob)
        signed_tx_to_bob = {"transaction": tx_data_to_bob, "signature": signature_to_bob, "public_key": alice_public}
        
        response = requests.post(f"{BASE_URL}/transactions", json=signed_tx_to_bob)
        assert response.status_code == 201
        print_status("Transaction from Alice to Bob accepted. Check the panel.")
        time.sleep(5)

        # 7. The Miner mines the final block
        print_status("Step 5: Mining the final block...")
        mine_request_3 = {"miner_address": miner_address}
        response = requests.post(f"{BASE_URL}/blocks/mine", json=mine_request_3)
        assert response.status_code == 201
        print_status("Final block mined.")
        print("-" * 50)
        time.sleep(3)

        # 8. Check final balances
        print_status("Step 6: Verifying all final balances...")
        
        alice_balance = requests.get(f"{BASE_URL}/balance/{alice_address}").json()['balance']
        bob_balance = requests.get(f"{BASE_URL}/balance/{bob_address}").json()['balance']
        miner_balance_final = requests.get(f"{BASE_URL}/balance/{miner_address}").json()['balance']
        
        print_status(f"Alice's final balance: {alice_balance}")
        print_status(f"Bob's final balance:   {bob_balance}")
        print_status(f"Miner's final balance: {miner_balance_final}")
        print("-" * 50)
        print_status("Simulation completed successfully!", is_ok=True)

    except (requests.exceptions.ConnectionError, AssertionError) as e:
        print_status(f"Simulation failed: {e}", is_ok=False)
        print("Please ensure the FastAPI server is running and accessible at", BASE_URL)

if __name__ == "__main__":
    run_simulation()
