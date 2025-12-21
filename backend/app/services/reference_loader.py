from pathlib import Path
from typing import Optional, List, Dict
from app.core.config import settings
from app.core.logger import logger


class ReferenceLoader:
    """
    Carregador de imagens de referência para comparação visual.
    
    Estrutura de diretórios para MOTOR:
    data/references/
    └── HONDA/
        └── MOTOR/
            └── {ANO}/
                └── {PREFIXO}.jpg  (ex: MC27E.jpg, MD09E1.jpg)
    
    OU estrutura simplificada:
    data/references/
    └── HONDA/
        └── {ANO}/
            └── motor.jpg
    """
    
    BASE_PATH = settings.REFERENCES_DIR
    SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
    
    @classmethod
    def get_motor_reference(
        cls,
        year: int,
        prefix: Optional[str] = None
    ) -> Optional[str]:
        """
        Busca imagem de referência de motor.
        
        Args:
            year: Ano do veículo
            prefix: Prefixo do motor (ex: MC27E) - opcional
            
        Returns:
            Caminho do arquivo ou None
        """
        search_paths = []
        
        # 1. Caminho específico com prefixo
        if prefix:
            prefix_clean = prefix.upper().replace('-', '')
            search_paths.append(
                cls.BASE_PATH / "HONDA" / "MOTOR" / str(year) / prefix_clean
            )
            search_paths.append(
                cls.BASE_PATH / "HONDA" / str(year) / prefix_clean
            )
        
        # 2. Caminho genérico por ano
        search_paths.append(cls.BASE_PATH / "HONDA" / "MOTOR" / str(year) / "motor")
        search_paths.append(cls.BASE_PATH / "HONDA" / str(year) / "motor")
        
        # 3. Fallback: anos próximos
        for offset in [-1, 1, -2, 2]:
            alt_year = year + offset
            if prefix:
                search_paths.append(
                    cls.BASE_PATH / "HONDA" / "MOTOR" / str(alt_year) / prefix.upper()
                )
            search_paths.append(
                cls.BASE_PATH / "HONDA" / "MOTOR" / str(alt_year) / "motor"
            )
            search_paths.append(
                cls.BASE_PATH / "HONDA" / str(alt_year) / "motor"
            )
        
        # 4. Fallback: referência padrão
        search_paths.append(cls.BASE_PATH / "HONDA" / "MOTOR" / "default" / "motor")
        search_paths.append(cls.BASE_PATH / "HONDA" / "default" / "motor")
        
        # Tenta encontrar
        for path in search_paths:
            found = cls._find_with_extensions(path)
            if found:
                logger.debug(f"Referência encontrada: {found}")
                return str(found)
        
        logger.warning(f"Referência não encontrada para Honda Motor {year} (prefix: {prefix})")
        return None
    
    @classmethod
    def _find_with_extensions(cls, base_path: Path) -> Optional[Path]:
        """Tenta encontrar arquivo com qualquer extensão suportada."""
        for ext in cls.SUPPORTED_EXTENSIONS:
            full_path = base_path.with_suffix(ext)
            if full_path.exists():
                return full_path
        
        if base_path.exists() and base_path.is_file():
            return base_path
        
        return None
    
    @classmethod
    def list_available_references(cls) -> Dict:
        """Lista todas as referências de motor disponíveis."""
        references = []
        
        honda_path = cls.BASE_PATH / "HONDA"
        if not honda_path.exists():
            return {'total': 0, 'references': [], 'error': 'Diretório HONDA não existe'}
        
        # Procura em todas as subpastas
        for year_dir in honda_path.rglob('*'):
            if not year_dir.is_dir():
                continue
            
            for file in year_dir.iterdir():
                if file.is_file() and file.suffix.lower() in cls.SUPPORTED_EXTENSIONS:
                    references.append({
                        'year': year_dir.name,
                        'name': file.stem,
                        'path': str(file)
                    })
        
        return {
            'total': len(references),
            'references': references
        }
    
    @classmethod
    def ensure_directories(cls):
        """Cria estrutura de diretórios se não existir."""
        directories = [
            cls.BASE_PATH / "HONDA" / "MOTOR" / "default",
            cls.BASE_PATH / "HONDA" / "MOTOR" / "2020",
            cls.BASE_PATH / "HONDA" / "MOTOR" / "2021",
            cls.BASE_PATH / "HONDA" / "MOTOR" / "2022",
            cls.BASE_PATH / "HONDA" / "MOTOR" / "2023",
            cls.BASE_PATH / "HONDA" / "MOTOR" / "2024",
            settings.FONTS_DIR,
        ]
        
        for dir_path in directories:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Diretórios criados em: {cls.BASE_PATH}")
