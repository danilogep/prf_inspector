"""
Carregador de imagens de referência para comparação visual.
"""

import os
from pathlib import Path
from typing import Optional, Dict, List
from app.core.config import settings
from app.core.logger import logger


class ReferenceLoader:
    """
    Gerencia imagens de referência de motores Honda.
    
    Estrutura esperada:
    data/references/
    └── HONDA/
        └── MOTOR/
            └── {ANO}/
                └── {PREFIXO}.jpg
    """
    
    BASE_PATH = Path(settings.REFERENCES_DIR)
    
    @classmethod
    def ensure_directories(cls):
        """Cria estrutura de diretórios se não existir."""
        dirs_to_create = [
            cls.BASE_PATH,
            cls.BASE_PATH / "HONDA",
            cls.BASE_PATH / "HONDA" / "MOTOR",
            cls.BASE_PATH / "HONDA" / "MOTOR" / "default",
        ]
        
        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Diretórios de referência verificados: {cls.BASE_PATH}")
    
    @classmethod
    def get_motor_reference(
        cls, 
        year: int, 
        prefix: Optional[str] = None
    ) -> Optional[str]:
        """
        Busca imagem de referência para um motor.
        
        Args:
            year: Ano do modelo
            prefix: Prefixo do motor (ex: MD09E1)
            
        Returns:
            Caminho da imagem ou None
        """
        if not prefix:
            return None
        
        # Tenta ano exato
        ref_path = cls.BASE_PATH / "HONDA" / "MOTOR" / str(year) / f"{prefix}.jpg"
        if ref_path.exists():
            return str(ref_path)
        
        # Tenta anos próximos (±2)
        for delta in [1, -1, 2, -2]:
            ref_path = cls.BASE_PATH / "HONDA" / "MOTOR" / str(year + delta) / f"{prefix}.jpg"
            if ref_path.exists():
                return str(ref_path)
        
        # Tenta default
        ref_path = cls.BASE_PATH / "HONDA" / "MOTOR" / "default" / f"{prefix}.jpg"
        if ref_path.exists():
            return str(ref_path)
        
        return None
    
    @classmethod
    def list_available_references(cls) -> Dict:
        """Lista todas as referências disponíveis."""
        result = {
            "total": 0,
            "by_year": {},
            "prefixes": set()
        }
        
        motor_path = cls.BASE_PATH / "HONDA" / "MOTOR"
        
        if not motor_path.exists():
            return result
        
        for year_dir in motor_path.iterdir():
            if year_dir.is_dir():
                year = year_dir.name
                result["by_year"][year] = []
                
                for ref_file in year_dir.glob("*.jpg"):
                    prefix = ref_file.stem
                    result["by_year"][year].append(prefix)
                    result["prefixes"].add(prefix)
                    result["total"] += 1
        
        result["prefixes"] = sorted(list(result["prefixes"]))
        
        return result
    
    @classmethod
    def save_reference(
        cls,
        image_bytes: bytes,
        year: int,
        prefix: str
    ) -> Optional[str]:
        """
        Salva uma nova imagem de referência.
        
        Args:
            image_bytes: Bytes da imagem
            year: Ano do modelo
            prefix: Prefixo do motor
            
        Returns:
            Caminho onde foi salvo ou None se falhou
        """
        try:
            year_dir = cls.BASE_PATH / "HONDA" / "MOTOR" / str(year)
            year_dir.mkdir(parents=True, exist_ok=True)
            
            ref_path = year_dir / f"{prefix.upper()}.jpg"
            
            with open(ref_path, "wb") as f:
                f.write(image_bytes)
            
            logger.info(f"Referência salva: {ref_path}")
            return str(ref_path)
            
        except Exception as e:
            logger.error(f"Erro ao salvar referência: {e}")
            return None