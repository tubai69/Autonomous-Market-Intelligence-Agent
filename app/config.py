from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    llm_temperature: float = 0.2
    llm_timeout_seconds: int = 180

    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    coins: str = "bitcoin,ethereum,solana,ripple,cardano"
    vs_currency: str = "usd"

    fetch_interval_seconds: int = 900  # autonomous cycle every 15 min
    autonomous_enabled: bool = True
    db_path: str = "data/insights.db"

    @property
    def coin_list(self) -> list[str]:
        return [c.strip().lower() for c in self.coins.split(",") if c.strip()]


settings = Settings()
