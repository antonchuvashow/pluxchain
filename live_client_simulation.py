import requests
import time
from urllib.parse import urlparse

from config import settings
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
    response=requests.Response()
    try:
        # 1. Generate keys and addresses for Miner, Alice, and Bob
        miner_private, miner_public = settings.node_private_key, settings.node_public_key
        alice_private, alice_public = generate_keys()
        bob_private, bob_public = generate_keys()

        miner_address = get_address_from_public_key(miner_public)
        alice_address = get_address_from_public_key(alice_public)
        bob_address = get_address_from_public_key(bob_public)

        print_status("Generated cryptographic identities for a Miner, Alice, and Bob.")
        print(f"  - Miner's Address: {miner_address} (This miner will receive all mining rewards)")
        print(f"  - Alice's Address: {alice_address}")
        print(f"  - Bob's Address:   {bob_address}")
        print("-" * 50)

        # 2. The Miner earns the first coins by mining an empty block
        print_status("Шаг 1: Майнер начинает работу, чтобы заработать первые монеты в экосистеме...")
        # При запросе на майнинг, miner_address должен быть адресом того, кто получит награду.
        # В этой симуляции, это адрес нашего сгенерированного Майнера.
        response = requests.post(f"{BASE_URL}/blocks/mine")
        assert response.status_code == 201
        print_status(f"Блок замайнен! Майнер получил свою первую награду.")

        # 3. Verify the miner's initial balance
        response = requests.get(f"{BASE_URL}/balance/{miner_address}")
        miner_balance = response.json()["balance"]
        assert miner_balance > 0
        print_status(f"Проверен баланс Майнера: {miner_balance} монет.")
        print("-" * 50)

        # 4. The Miner (who now has funds) sends money to Alice
        print_status("Шаг 2: Майнер отправляет 10.0 монет Алисе...")
        tx_data_to_alice = {"sender": miner_address, "receiver": alice_address, "amount": 10.0, "timestamp": time.time()}
        signature_to_alice = sign_transaction(miner_private, tx_data_to_alice)
        signed_tx_to_alice = {"transaction": tx_data_to_alice, "signature": signature_to_alice, "public_key": miner_public}

        response = requests.post(f"{BASE_URL}/transactions", json=signed_tx_to_alice)
        assert response.status_code == 201
        print_status("Транзакция от Майнера к Алисе принята. Проверьте панель на наличие ожидающей транзакции.")

        # 5. The Miner mines the block with the transaction to Alice
        print_status("Шаг 3: Майнер майнит блок для подтверждения средств Алисы...")
        response = requests.post(f"{BASE_URL}/blocks/mine")
        assert response.status_code == 201
        print_status("Блок замайнен! Средства Алисы теперь подтверждены.")

        # 6. Alice sends money to Bob
        print_status("Шаг 4: Алиса отправляет 5.0 монет Бобу...")
        tx_data_to_bob = {"sender": alice_address, "receiver": bob_address, "amount": 5.0, "timestamp": time.time()}
        signature_to_bob = sign_transaction(alice_private, tx_data_to_bob)
        signed_tx_to_bob = {"transaction": tx_data_to_bob, "signature": signature_to_bob, "public_key": alice_public}

        response = requests.post(f"{BASE_URL}/transactions", json=signed_tx_to_bob)
        assert response.status_code == 201
        print_status("Транзакция от Алисы к Бобу принята. Проверьте панель.")

        # 7. The Miner mines the final block
        print_status("Шаг 5: Майнер майнит финальный блок...")
        response = requests.post(f"{BASE_URL}/blocks/mine")
        assert response.status_code == 201
        print_status("Финальный блок замайнен.")
        print("-" * 50)

        # 8. Check final balances
        print_status("Шаг 6: Проверяем все финальные балансы...")

        alice_balance = requests.get(f"{BASE_URL}/balance/{alice_address}").json()['balance']
        bob_balance = requests.get(f"{BASE_URL}/balance/{bob_address}").json()['balance']
        miner_balance_final = requests.get(f"{BASE_URL}/balance/{miner_address}").json()['balance']

        print_status(f"Финальный баланс Алисы: {alice_balance}")
        print_status(f"Финальный баланс Боба:   {bob_balance}")
        print_status(f"Финальный баланс Майнера: {miner_balance_final}")
        print("-" * 50)
        print_status("Симуляция успешно завершена!", is_ok=True)

    except (requests.exceptions.ConnectionError, AssertionError, ValueError) as e:
        print_status(f"Симуляция завершилась с ошибкой: {e}\n\t{response.text}", is_ok=False)
        print("Пожалуйста, убедитесь, что сервер FastAPI запущен и доступен по адресу", BASE_URL)

if __name__ == "__main__":
    run_simulation()
