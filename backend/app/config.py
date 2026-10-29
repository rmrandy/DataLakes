from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "datalake"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    nasa_api_key: str = "DEMO_KEY"
    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
