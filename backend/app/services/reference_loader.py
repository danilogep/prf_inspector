import os
from pathlib import Path
from app.core.logger import logger

class ReferenceLoader:
    # Ajuste o caminho se necessário dependendo de onde você roda o main.py
    BASE_PATH = Path("data/references")

    @staticmethod
    def get_image_path(brand: str, year: int, component: str) -> str:
        """Busca imagem: data/references/HONDA/2020/chassi.jpg"""
        try:
            # Tenta ano exato
            path = ReferenceLoader.BASE_PATH / brand.upper() / str(year) / f"{component}.jpg"
            if path.exists(): return str(path)
            
            # Tenta +/- 1 ano (fallback de geração)
            for offset in [-1, 1]:
                alt = ReferenceLoader.BASE_PATH / brand.upper() / str(year + offset) / f"{component}.jpg"
                if alt.exists(): return str(alt)
        except Exception as e:
            logger.error(f"Erro ao buscar referência: {e}")
            
        return None