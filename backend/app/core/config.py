from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "PRF Honda Inspector - Motor"
    DEBUG_MODE: bool = True
    
    # Caminhos do Sistema
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    REFERENCES_DIR: Path = BASE_DIR / "data" / "references"
    FONTS_DIR: Path = BASE_DIR / "data" / "fonts"
    
    # Tolerâncias para Análise Forense
    ALIGNMENT_TOLERANCE: float = 0.15  # 15% da altura da letra
    DENSITY_TOLERANCE: float = 0.30    # 30% de diferença na densidade de pontos
    SSIM_THRESHOLD: float = 0.55       # Mínimo de similaridade visual (0 a 1)
    
    # Caracteres mais falsificados (baseado na imagem de referência FAKE)
    # Estes recebem análise mais rigorosa
    HIGH_RISK_CHARS: List[str] = ['0', '1', '3', '4', '9']
    
    # Limiar de pontos para classificar como micropunção
    MICROPOINT_DOT_THRESHOLD: float = 3.5
    
    # Ano de transição estampagem -> laser (2010 em diante é laser/micropunção)
    LASER_TRANSITION_YEAR: int = 2010
    
    # Tolerância para detecção de vazamentos na fonte (gaps característicos)
    GAP_DETECTION_THRESHOLD: float = 0.20  # 20% de tolerância

    class Config:
        env_file = ".env"

settings = Settings()
