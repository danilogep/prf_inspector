import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from typing import Dict, Optional
from app.services.ocr import OCREngine
from app.core.config import settings
from app.core.logger import logger


class VisualMatcher:
    """
    Comparador visual de gravações de motor.
    Compara a foto enviada com imagens de referência do banco de dados.
    """
    
    def __init__(self):
        self.ocr = OCREngine()
    
    def compare(self, user_image_bytes: bytes, ref_path: Optional[str]) -> Dict:
        """
        Compara imagem do usuário com referência.
        
        Args:
            user_image_bytes: Bytes da imagem enviada
            ref_path: Caminho da imagem de referência
            
        Returns:
            Dict com resultado da comparação
        """
        result = {
            'status': 'SEM_REFERÊNCIA',
            'similarity': 0.0,
            'reference_used': None,
            'details': ''
        }
        
        if not ref_path:
            result['details'] = "Nenhuma imagem de referência disponível para comparação"
            return result
        
        try:
            # Carrega imagens
            nparr = np.frombuffer(user_image_bytes, np.uint8)
            user_img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            ref_img = cv2.imread(ref_path, cv2.IMREAD_GRAYSCALE)
            
            if user_img is None:
                result['status'] = 'ERRO'
                result['details'] = "Erro ao processar imagem do usuário"
                return result
            
            if ref_img is None:
                result['status'] = 'ERRO'
                result['details'] = f"Erro ao carregar referência: {ref_path}"
                return result
            
            result['reference_used'] = ref_path
            
            # Normaliza tamanhos para comparação
            target_size = (400, 150)
            user_resized = cv2.resize(user_img, target_size)
            ref_resized = cv2.resize(ref_img, target_size)
            
            # Equaliza histograma para normalizar iluminação
            user_eq = cv2.equalizeHist(user_resized)
            ref_eq = cv2.equalizeHist(ref_resized)
            
            # Calcula SSIM
            similarity, _ = ssim(user_eq, ref_eq, full=True)
            result['similarity'] = round(similarity * 100, 1)
            
            # Determina status
            if similarity >= settings.SSIM_THRESHOLD:
                result['status'] = 'COMPATÍVEL'
                result['details'] = "Padrão visual compatível com referência"
            else:
                result['status'] = 'DIVERGENTE'
                result['details'] = f"Similaridade {result['similarity']}% abaixo do limiar ({settings.SSIM_THRESHOLD*100}%)"
            
            return result
            
        except Exception as e:
            logger.error(f"Erro na comparação visual: {e}")
            result['status'] = 'ERRO'
            result['details'] = f"Erro na comparação: {str(e)}"
            return result
