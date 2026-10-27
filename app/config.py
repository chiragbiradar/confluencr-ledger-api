from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://ledger:ledger@localhost:5432/ledger"
    TEST_DATABASE_URL: str = "postgresql+psycopg://ledger:ledger@localhost:5432/ledger_test"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
