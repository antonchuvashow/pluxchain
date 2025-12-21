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
    # The address of this node, which will be shared with other nodes
    my_address: Optional[str] = "127.0.0.1:8000"
    # A list of trusted "seed" nodes to connect to on startup
    seed_nodes: List[str] = []

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
