from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    project_name: str = "Wishlist API"
    backend_cors_origins: list[str] = ["*"]

    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_user: str = "wishlist"
    postgres_password: str = "wishlist"
    postgres_db: str = "wishlist"

    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True

    class Config:
        env_file = ".env"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
