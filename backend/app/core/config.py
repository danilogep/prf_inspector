"""
Configurações do PRF Honda Inspector v5.16
==========================================
REFATORAÇÃO COMPLETA

CORREÇÕES:
1. Carregamento robusto do .env
2. Validação de configurações
3. Valores padrão seguros
4. Type hints completos
"""

import os
from pathlib import Path
from typing import List, Optional, Any
from functools import lru_cache
from dotenv import load_dotenv


def find_and_load_env() -> Optional[Path]:
    """
    Procura e carrega o arquivo .env em vários locais possíveis.
    
    Returns:
        Path do arquivo carregado ou None
    """
    # Diretório base
    config_dir = Path(__file__).parent  # app/core/
    app_dir = config_dir.parent          # app/
    backend_dir = app_dir.parent         # backend/
    project_dir = backend_dir.parent     # PRF_Inspector/
    
    # Lista de possíveis locais (em ordem de prioridade)
    possible_locations = [
        backend_dir / ".env",
        project_dir / ".env",
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
    ]
    
    for env_path in possible_locations:
        try:
            if env_path.exists():
                load_dotenv(env_path, override=True)
                print(f"✓ Arquivo .env carregado: {env_path}")
                return env_path
        except Exception as e:
            print(f"⚠ Erro ao tentar {env_path}: {e}")
            continue
    
    # Tenta load_dotenv padrão
    print("⚠ Arquivo .env não encontrado, usando variáveis de ambiente")
    load_dotenv()
    return None


def clean_api_key(key: Optional[str]) -> str:
    """
    Remove caracteres inválidos da API key.
    
    Args:
        key: Chave bruta
        
    Returns:
        Chave limpa
    """
    if not key:
        return ''
    
    # Remove espaços, aspas, quebras de linha
    key = key.strip()
    key = key.strip('"').strip("'")
    key = key.replace('\n', '').replace('\r', '')
    key = key.replace(' ', '')
    
    return key


def get_env_bool(key: str, default: bool = False) -> bool:
    """
    Obtém valor booleano de variável de ambiente.
    
    Args:
        key: Nome da variável
        default: Valor padrão
        
    Returns:
        Valor booleano
    """
    value = os.getenv(key, '').lower()
    if value in ('true', '1', 'yes', 'on'):
        return True
    elif value in ('false', '0', 'no', 'off'):
        return False
    return default


def get_env_int(key: str, default: int) -> int:
    """
    Obtém valor inteiro de variável de ambiente.
    
    Args:
        key: Nome da variável
        default: Valor padrão
        
    Returns:
        Valor inteiro
    """
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def get_env_list(key: str, default: List[str] = None) -> List[str]:
    """
    Obtém lista de strings de variável de ambiente.
    
    Args:
        key: Nome da variável
        default: Valor padrão
        
    Returns:
        Lista de strings
    """
    if default is None:
        default = []
    
    value = os.getenv(key, '')
    if not value:
        return default
    
    return [item.strip() for item in value.split(',') if item.strip()]


# Carrega .env
env_loaded = find_and_load_env()

# Obtém e valida API key
raw_api_key = os.getenv('ANTHROPIC_API_KEY', '')
api_key = clean_api_key(raw_api_key)

if api_key:
    print(f"✓ ANTHROPIC_API_KEY encontrada: {api_key[:20]}...")
    if len(api_key) < 50:
        print(f"⚠ AVISO: Chave parece curta ({len(api_key)} chars)")
    if not api_key.startswith('sk-ant-'):
        print(f"⚠ AVISO: Chave não começa com 'sk-ant-'")
else:
    print("✗ ANTHROPIC_API_KEY não encontrada - IA desabilitada")


class Settings:
    """
    Configurações da aplicação.
    
    Todas as configurações são carregadas de variáveis de ambiente
    com valores padrão seguros.
    """
    
    # ========================================
    # API Principal
    # ========================================
    
    API_HOST: str = os.getenv('API_HOST', '0.0.0.0')
    API_PORT: int = get_env_int('API_PORT', 8000)
    DEBUG_MODE: bool = get_env_bool('DEBUG_MODE', False)
    
    # ========================================
    # Anthropic API
    # ========================================
    
    ANTHROPIC_API_KEY: str = api_key
    ANTHROPIC_MODEL: str = os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')
    ANTHROPIC_TIMEOUT: int = get_env_int('ANTHROPIC_TIMEOUT', 180)
    
    # ========================================
    # Supabase
    # ========================================
    
    SUPABASE_URL: Optional[str] = os.getenv('SUPABASE_URL')
    SUPABASE_KEY: Optional[str] = os.getenv('SUPABASE_KEY')
    
    # ========================================
    # Segurança
    # ========================================
    
    CORS_ORIGINS: List[str] = get_env_list('CORS_ORIGINS', ['*'])
    RATE_LIMIT_PER_MINUTE: int = get_env_int('RATE_LIMIT_PER_MINUTE', 60)
    MAX_UPLOAD_SIZE: int = get_env_int('MAX_UPLOAD_SIZE', 10 * 1024 * 1024)  # 10MB
    
    # ========================================
    # Análise
    # ========================================
    
    LASER_TRANSITION_YEAR: int = get_env_int('LASER_TRANSITION_YEAR', 2010)
    MIN_CONFIDENCE_THRESHOLD: float = float(os.getenv('MIN_CONFIDENCE_THRESHOLD', '0.7'))
    
    # ========================================
    # Cache
    # ========================================
    
    CACHE_ENABLED: bool = get_env_bool('CACHE_ENABLED', True)
    CACHE_TTL: int = get_env_int('CACHE_TTL', 3600)  # 1 hora
    
    # ========================================
    # Diretórios
    # ========================================
    
    @property
    def BASE_DIR(self) -> Path:
        """Diretório base do projeto."""
        return Path(__file__).parent.parent.parent
    
    @property
    def DATA_DIR(self) -> Path:
        """Diretório de dados."""
        return self.BASE_DIR / "data"
    
    @property
    def FONTS_DIR(self) -> Path:
        """Diretório de fontes."""
        return self.DATA_DIR / "fonts"
    
    @property
    def REFERENCES_DIR(self) -> Path:
        """Diretório de referências."""
        return self.DATA_DIR / "references"
    
    def validate(self) -> bool:
        """
        Valida configurações críticas.
        
        Returns:
            True se todas as configurações críticas estão OK
        """
        warnings = []
        errors = []
        
        # Verifica API key
        if not self.ANTHROPIC_API_KEY:
            warnings.append("ANTHROPIC_API_KEY não configurada - IA desabilitada")
        
        # Verifica Supabase
        if not self.SUPABASE_URL or not self.SUPABASE_KEY:
            warnings.append("Supabase não configurado - persistência desabilitada")
        
        # Verifica diretórios
        if not self.DATA_DIR.exists():
            warnings.append(f"Diretório de dados não existe: {self.DATA_DIR}")
        
        # Imprime avisos
        for warning in warnings:
            print(f"⚠ {warning}")
        
        for error in errors:
            print(f"✗ {error}")
        
        return len(errors) == 0
    
    def __repr__(self) -> str:
        """Representação segura (sem expor secrets)."""
        return f"""Settings(
    API_HOST={self.API_HOST!r},
    API_PORT={self.API_PORT},
    DEBUG_MODE={self.DEBUG_MODE},
    ANTHROPIC_API_KEY={'***' if self.ANTHROPIC_API_KEY else 'None'},
    SUPABASE_URL={'***' if self.SUPABASE_URL else 'None'},
    RATE_LIMIT={self.RATE_LIMIT_PER_MINUTE}/min
)"""


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna instância singleton das configurações.
    
    Returns:
        Instância de Settings
    """
    return Settings()


# Instância global para compatibilidade
settings = get_settings()

# Valida configurações na inicialização
settings.validate()
