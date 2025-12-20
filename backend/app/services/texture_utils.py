import cv2
import numpy as np

class TextureUtils:
    """Funções compartilhadas de processamento de imagem com OpenCV."""
    
    @staticmethod
    def preprocess(image_bytes: bytes):
        """Converte bytes para imagem OpenCV e cria versão binária."""
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Falha ao decodificar imagem")
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Threshold adaptativo é essencial para metal com reflexo
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 11, 2
        )
        return img, gray, thresh

    @staticmethod
    def get_roi(img, bbox):
        """Recorta a região de interesse (ROI) baseada no BBox do OCR."""
        (tl, tr, br, bl) = bbox
        
        # Garante coordenadas inteiras e dentro da imagem
        y_min = int(max(0, min(tl[1], tr[1])))
        y_max = int(min(img.shape[0], max(bl[1], br[1])))
        x_min = int(max(0, min(tl[0], bl[0])))
        x_max = int(min(img.shape[1], max(tr[0], br[0])))
        
        return img[y_min:y_max, x_min:x_max]

    @staticmethod
    def count_dots(roi_binary):
        """Conta ilhas brancas (blobs) em fundo preto."""
        if roi_binary.size == 0: return 0
        contours, _ = cv2.findContours(roi_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # Filtra ruídos muito pequenos (< 2 pixels)
        return len([c for c in contours if cv2.contourArea(c) > 2])