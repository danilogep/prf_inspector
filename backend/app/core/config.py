from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "PRF Honda Inspector"
    DEBUG_MODE: bool = True
    
    # Tolerâncias para Análise Forense
    ALIGNMENT_TOLERANCE: float = 0.20  # 20% da altura da letra
    DENSITY_TOLERANCE: float = 0.45    # 45% de diferença na densidade de pontos
    SSIM_THRESHOLD: float = 0.45       # Mínimo de similaridade visual (0 a 1)

    class Config:
        env_file = ".env"

settings = Settings()