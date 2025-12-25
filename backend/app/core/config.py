"""
Configurações do PRF Honda Inspector v3.2
=========================================
Configuração centralizada de caminhos e armazenamento.
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Carrega .env
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ Arquivo .env carregado: {env_path}")
else:
    load_dotenv()

# Verifica API Key
api_key = os.getenv('ANTHROPIC_API_KEY', '')
if api_key:
    print(f"✓ ANTHROPIC_API_KEY encontrada: {api_key[:20]}...")
else:
    print("✗ ANTHROPIC_API_KEY não encontrada")


class Settings:
    """Configurações da aplicação."""
    
    APP_NAME: str = "PRF Honda Inspector"
    VERSION: str = "3.2.0"
    DEBUG_MODE: bool = True
    
    # ============================================================
    # CAMINHOS DE ARMAZENAMENTO
    # ============================================================
    
    # Diretório base do backend
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    
    # Diretório de dados
    DATA_DIR: Path = BASE_DIR / "data"
    
    # Fontes Honda (única pasta para LASER e ESTAMPAGEM)
    FONTS_DIR: Path = DATA_DIR / "honda_fonts"
    
    # Imagens de referência por modelo/ano
    REFERENCES_DIR: Path = DATA_DIR / "references"
    
    # Histórico de análises (local)
    ANALYSIS_DIR: Path = DATA_DIR / "analysis_history"
    
    # Logs
    LOGS_DIR: Path = BASE_DIR / "logs"
    
    # ============================================================
    # API KEYS (do arquivo .env)
    # ============================================================
    
    ANTHROPIC_API_KEY: str = os.getenv('ANTHROPIC_API_KEY', '')
    SUPABASE_URL: str = os.getenv('SUPABASE_URL', '')
    SUPABASE_KEY: str = os.getenv('SUPABASE_KEY', '')
    
    # ============================================================
    # CONFIGURAÇÕES DE ANÁLISE FORENSE
    # ============================================================
    
    # Tolerâncias
    ALIGNMENT_TOLERANCE: float = 0.15      # 15% da altura
    DENSITY_TOLERANCE: float = 0.30        # 30% diferença
    SSIM_THRESHOLD: float = 0.55           # Mínimo similaridade
    
    # Caracteres de alto risco (mais adulterados)
    HIGH_RISK_CHARS: List[str] = ['0', '1', '3', '4', '9']
    
    # Ano de transição ESTAMPAGEM → LASER
    LASER_TRANSITION_YEAR: int = 2010
    
    # ============================================================
    # CONFIGURAÇÕES DE ARMAZENAMENTO SUPABASE
    # ============================================================
    
    # Bucket para imagens de análise
    SUPABASE_BUCKET_ANALYSIS: str = "analysis-images"
    
    # Bucket para fontes (backup)
    SUPABASE_BUCKET_FONTS: str = "honda-fonts"
    
    # Tabela de histórico
    SUPABASE_TABLE_HISTORY: str = "analysis_history"
    
    # Tabela de fraudes conhecidas
    SUPABASE_TABLE_FRAUDS: str = "known_frauds"


settings = Settings()


def ensure_directories():
    """Cria diretórios necessários se não existirem."""
    dirs = [
        settings.DATA_DIR,
        settings.FONTS_DIR,
        settings.REFERENCES_DIR,
        settings.ANALYSIS_DIR,
        settings.LOGS_DIR,
    ]
    
    for dir_path in dirs:
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"  Criado: {dir_path}")


# Cria diretórios ao importar
ensure_directories()

# Log das configurações
print(f"BASE_DIR: {settings.BASE_DIR}")
print(f"FONTS_DIR: {settings.FONTS_DIR}")
print(f"IA habilitada: {bool(settings.ANTHROPIC_API_KEY)}")
