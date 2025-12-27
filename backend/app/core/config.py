"""
Configurações do PRF Honda Inspector v5.7.1
===========================================
Configuração centralizada com correção de carregamento do .env
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# ============================================================
# CORREÇÃO: Tenta carregar .env de múltiplos locais
# ============================================================

def find_and_load_env():
    """Procura e carrega o arquivo .env em vários locais possíveis."""
    
    # Diretório base do config.py
    config_dir = Path(__file__).parent  # app/core/
    app_dir = config_dir.parent          # app/
    backend_dir = app_dir.parent         # backend/
    project_dir = backend_dir.parent     # PRF_Inspector/
    
    # Lista de possíveis locais do .env (em ordem de prioridade)
    possible_locations = [
        backend_dir / ".env",           # backend/.env (mais comum)
        project_dir / ".env",           # PRF_Inspector/.env
        project_dir / "backend" / ".env",
        Path.cwd() / ".env",            # Diretório atual
        Path.cwd() / "backend" / ".env",
        app_dir / ".env",               # app/.env
        Path(os.path.expanduser("~")) / ".env",  # Home do usuário
    ]
    
    # Tenta cada local
    for env_path in possible_locations:
        try:
            if env_path.exists():
                load_dotenv(env_path, override=True)
                print(f"✓ Arquivo .env carregado: {env_path}")
                return env_path
        except Exception as e:
            print(f"⚠ Erro ao tentar {env_path}: {e}")
            continue
    
    # Se não encontrou nenhum, tenta load_dotenv padrão
    print("⚠ Arquivo .env não encontrado nos locais esperados")
    print("  Tentando load_dotenv() padrão...")
    load_dotenv()
    
    return None

# Carrega o .env
env_loaded = find_and_load_env()

# ============================================================
# VERIFICAÇÃO E LIMPEZA DA API KEY
# ============================================================

def clean_api_key(key: str) -> str:
    """Remove caracteres inválidos da API key."""
    if not key:
        return ''
    # Remove espaços, aspas, quebras de linha
    key = key.strip()
    key = key.strip('"').strip("'")
    key = key.replace('\n', '').replace('\r', '')
    return key

# Obtém e limpa a API Key
raw_api_key = os.getenv('ANTHROPIC_API_KEY', '')
api_key = clean_api_key(raw_api_key)

if api_key:
    print(f"✓ ANTHROPIC_API_KEY encontrada: {api_key[:20]}...")
    if len(api_key) < 50:
        print(f"⚠ AVISO: Chave parece curta ({len(api_key)} chars)")
    if not api_key.startswith('sk-ant-'):
        print(f"⚠ AVISO: Chave não começa com 'sk-ant-'")
else:
    print("✗ ANTHROPIC_API_KEY não encontrada")


class Settings:
    """Configurações da aplicação."""
    
    APP_NAME: str = "PRF Honda Inspector"
    VERSION: str = "5.7.1"
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
    # API KEYS (já limpas e validadas)
    # ============================================================
    
    ANTHROPIC_API_KEY: str = api_key  # Usa a chave já limpa
    SUPABASE_URL: str = clean_api_key(os.getenv('SUPABASE_URL', ''))
    SUPABASE_KEY: str = clean_api_key(os.getenv('SUPABASE_KEY', ''))
    
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
