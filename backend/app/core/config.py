from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Structura"
    environment: str = "development"

settings = Settings()
