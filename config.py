from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings are loaded from environment variables.
    Pydantic-settings will automatically match environment variables to the fields in this class.
    For example, DATABASE_URL will map to `database_url`.
    """
    # --- Database ---
    database_url: str = "db/block.sqlite"

    # --- Blockchain ---
    mining_reward: float = 10.0
    difficulty: int = 4  # The number of leading zeros for a valid hash
    
    # --- Web Panel ---
    # The address that receives rewards when mining is triggered from the web panel
    panel_miner_address: str = "0" * 40

    # --- Pydantic-Settings Configuration ---
    # This tells pydantic-settings to look for a .env file if you want to use one.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Create a single, importable instance of the settings
settings = Settings()
