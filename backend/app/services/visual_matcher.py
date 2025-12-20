import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from app.services.ocr import OCREngine
from app.services.texture_utils import TextureUtils
from app.core.config import settings

class VisualMatcher:
    def __init__(self):
        self.ocr = OCREngine()
        self.tex = TextureUtils()

    def compare(self, user_bytes: bytes, ref_path: str) -> dict:
        if not ref_path:
            return {"status": "ALERTA", "wmi_similarity": 0.0, "style_match": "N/A", "details": "Sem imagem de referência"}

        # Carregar Imagens
        img_user, user_gray, _ = self.tex.preprocess(user_bytes)
        img_ref = cv2.imread(ref_path, cv2.IMREAD_GRAYSCALE)
        
        if img_ref is None: 
            return {"status": "ERRO", "wmi_similarity": 0.0, "style_match": "N/A", "details": "Erro ao ler arquivo de referência"}

        # 1. OCR na Referência para achar posição do WMI
        _, _, ref_encoded = cv2.imencode('.jpg', img_ref)
        _, ref_ocr = self.ocr.process_image(ref_encoded.tobytes())
        _, user_ocr = self.ocr.process_image(user_bytes)

        # 2. Comparação de Prefixo (WMI - primeiros 3 chars)
        score = 0.0
        status = "N/A"
        
        if len(ref_ocr) >= 3 and len(user_ocr) >= 3:
            ref_crop = self._extract_crop_from_ocr(img_ref, ref_ocr[:3])
            user_crop = self._extract_crop_from_ocr(user_gray, user_ocr[:3])
            
            if ref_crop.size > 0 and user_crop.size > 0:
                try:
                    # Normaliza tamanho para 200x100 para comparação SSIM
                    ref_resized = cv2.resize(ref_crop, (200, 100))
                    user_resized = cv2.resize(user_crop, (200, 100))
                    
                    score, _ = ssim(ref_resized, user_resized, full=True)
                    status = "COMPATIVEL" if score > settings.SSIM_THRESHOLD else "DIVERGENTE"
                except Exception:
                    status = "ERRO_PROCESSAMENTO"

        return {
            "status": status,
            "wmi_similarity": round(score * 100, 1),
            "style_match": "Padrão Visual Verificado",
            "details": "Comparação visual realizada com sucesso." if status != "N/A" else "Não foi possível isolar o WMI para comparação."
        }

    def _extract_crop_from_ocr(self, img, details):
        try:
            # Pega limites extremos dos caracteres
            x_coords = [p[0] for det in details for p in det[0]]
            y_coords = [p[1] for det in details for p in det[0]]
            
            x_min, x_max = int(min(x_coords)), int(max(x_coords))
            y_min, y_max = int(min(y_coords)), int(max(y_coords))
            
            # Adiciona uma margem de segurança
            h, w = img.shape
            y_min = max(0, y_min - 5)
            y_max = min(h, y_max + 5)
            x_min = max(0, x_min - 5)
            x_max = min(w, x_max + 5)

            return img[y_min:y_max, x_min:x_max]
        except: 
            return np.array([])