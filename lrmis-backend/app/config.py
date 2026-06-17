from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017"
    db_name: str = "lrmis"
    app_env: str = "development"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
