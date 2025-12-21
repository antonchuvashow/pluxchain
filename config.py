from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    """
    Application settings are loaded from environment variables.
    """
    # --- Database ---
    database_url: str = "db/block.sqlite"

    # --- Blockchain ---
    system_address: str = "0" * 40
    mining_reward: float = 10.0
    difficulty: int = 4

    # --- Web Panel ---
    panel_miner_address: str = "0" * 40
    
    # --- Networking ---
    # The network address (host:port) of this node, which will be shared with other nodes
    my_network_address: Optional[str] = "127.0.0.1:8000"
    # A list of trusted "seed" nodes to connect to on startup
    seed_nodes: List[str] = []

    # --- Node's Cryptographic Identity ---
    # Private key of the node, used for signing transactions if the node itself needs to send them
    node_private_key: Optional[str] = None
    # Public key of the node, from which its blockchain address is derived
    node_public_key: Optional[str] = None
    # The blockchain address of the node, derived from its public key
    node_blockchain_address: Optional[str] = None


    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
