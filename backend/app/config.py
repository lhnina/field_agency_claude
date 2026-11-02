from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FA_", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres@localhost:5432/fieldagency"
    jwt_secret: str = "dev-only-change-me-in-production-please-32b"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 10
    cors_origins: list[str] = ["http://localhost:5173"]
    # Horizonte por defeito para gerar ocorrências (dias a partir de hoje)
    horizonte_planeamento_dias: int = 56
    # Limites laborais (Código do Trabalho; sem IRCT aplicável)
    limite_horas_dia: float = 8.0
    limite_horas_semana: float = 40.0


settings = Settings()
