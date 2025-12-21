import cv2
import numpy as np
import easyocr
from typing import Tuple, List, Optional
from app.core.logger import logger


class OCREngine:
    """
    Motor de OCR otimizado para leitura de gravações em metal (motor Honda).
    
    Técnicas aplicadas:
    - CLAHE para equalização adaptativa (lida com reflexos)
    - Bilateral filter para remoção de ruído preservando bordas
    - Threshold adaptativo para binarização
    - Fusão de múltiplas passagens de OCR
    """
    
    def __init__(self, use_gpu: bool = False):
        logger.info("Inicializando OCR Engine...")
        self.reader = easyocr.Reader(
            ['en'],
            gpu=use_gpu,
            verbose=False
        )
        self.confidence_threshold = 0.35
        logger.info("OCR Engine pronto")
    
    def preprocess_metal_image(self, image_bytes: bytes) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Pré-processamento específico para gravações em superfície metálica.
        
        Returns:
            Tuple: (imagem_colorida, imagem_cinza, imagem_binária)
        """
        # Decodifica
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("Falha ao decodificar imagem")
        
        # Converte para escala de cinza
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # CLAHE - melhora contraste em áreas com reflexo
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Bilateral filter - remove ruído preservando bordas
        denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
        
        # Threshold adaptativo
        binary = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=15,
            C=4
        )
        
        return img, gray, binary
    
    def process_image(
        self, 
        image_bytes: bytes,
        extract_char_images: bool = True
    ) -> Tuple[str, List, Optional[List[Tuple[np.ndarray, str, int]]]]:
        """
        Processa imagem e extrai texto via OCR.
        
        Args:
            image_bytes: Bytes da imagem
            extract_char_images: Se True, retorna imagens individuais dos caracteres
            
        Returns:
            Tuple: (texto_completo, detalhes_ocr, lista_caracteres)
        """
        try:
            # Pré-processamento
            img_color, img_gray, img_binary = self.preprocess_metal_image(image_bytes)
            
            # OCR na imagem original
            result_original = self.reader.readtext(image_bytes, detail=1)
            
            # OCR na imagem pré-processada (pode pegar caracteres que o original perdeu)
            _, enhanced_encoded = cv2.imencode('.jpg', img_binary)
            result_enhanced = self.reader.readtext(enhanced_encoded.tobytes(), detail=1)
            
            # Combina resultados
            combined = self._merge_results(result_original, result_enhanced)
            
            # Filtra por confiança
            filtered = [r for r in combined if r[2] >= self.confidence_threshold]
            
            # Ordena da esquerda para direita, depois de cima para baixo
            filtered.sort(key=lambda x: (min(p[1] for p in x[0]), min(p[0] for p in x[0])))
            
            # Concatena texto
            full_text = ""
            for bbox, text, conf in filtered:
                clean = ''.join(c for c in text if c.isalnum() or c == '-')
                full_text += clean
            
            full_text = full_text.upper()
            
            # Extrai imagens individuais
            char_images = None
            if extract_char_images:
                char_images = self._extract_char_images(img_gray, filtered)
            
            logger.info(f"OCR detectou: '{full_text}' ({len(filtered)} detecções)")
            
            return full_text, filtered, char_images
            
        except Exception as e:
            logger.error(f"Erro no OCR: {e}")
            raise
    
    def _merge_results(self, results1: List, results2: List) -> List:
        """Mescla resultados de duas passagens de OCR evitando duplicatas."""
        merged = list(results1)
        
        for bbox2, text2, conf2 in results2:
            is_duplicate = False
            
            for i, (bbox1, text1, conf1) in enumerate(merged):
                if self._boxes_overlap(bbox1, bbox2):
                    # Mantém o de maior confiança
                    if conf2 > conf1:
                        merged[i] = (bbox2, text2, conf2)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                merged.append((bbox2, text2, conf2))
        
        return merged
    
    def _boxes_overlap(self, bbox1, bbox2, threshold: float = 0.4) -> bool:
        """Verifica se dois bounding boxes se sobrepõem."""
        def to_rect(bbox):
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            return min(xs), min(ys), max(xs), max(ys)
        
        r1 = to_rect(bbox1)
        r2 = to_rect(bbox2)
        
        # Interseção
        x_left = max(r1[0], r2[0])
        y_top = max(r1[1], r2[1])
        x_right = min(r1[2], r2[2])
        y_bottom = min(r1[3], r2[3])
        
        if x_right < x_left or y_bottom < y_top:
            return False
        
        intersection = (x_right - x_left) * (y_bottom - y_top)
        area1 = (r1[2] - r1[0]) * (r1[3] - r1[1])
        area2 = (r2[2] - r2[0]) * (r2[3] - r2[1])
        
        iou = intersection / max(area1 + area2 - intersection, 1)
        return iou > threshold
    
    def _extract_char_images(
        self, 
        img_gray: np.ndarray, 
        ocr_results: List
    ) -> List[Tuple[np.ndarray, str, int]]:
        """
        Extrai imagens individuais de cada caractere.
        
        Returns:
            Lista de (imagem, caractere, posição)
        """
        char_images = []
        position = 0
        
        for bbox, text, conf in ocr_results:
            # Coordenadas do bbox
            xs = [int(p[0]) for p in bbox]
            ys = [int(p[1]) for p in bbox]
            
            x_min = max(0, min(xs) - 3)
            x_max = min(img_gray.shape[1], max(xs) + 3)
            y_min = max(0, min(ys) - 3)
            y_max = min(img_gray.shape[0], max(ys) + 3)
            
            roi = img_gray[y_min:y_max, x_min:x_max]
            
            if roi.size == 0:
                continue
            
            # Se o texto tem múltiplos caracteres, tenta separar
            text_clean = ''.join(c for c in text if c.isalnum())
            
            if len(text_clean) == 1:
                position += 1
                char_images.append((roi.copy(), text_clean.upper(), position))
            elif len(text_clean) > 1:
                # Divide o ROI proporcionalmente
                char_width = roi.shape[1] // len(text_clean)
                for i, char in enumerate(text_clean):
                    if char.isalnum():
                        position += 1
                        x1 = i * char_width
                        x2 = (i + 1) * char_width if i < len(text_clean) - 1 else roi.shape[1]
                        char_roi = roi[:, x1:x2]
                        if char_roi.size > 0:
                            char_images.append((char_roi.copy(), char.upper(), position))
        
        return char_images
    
    def get_character_metrics(self, image_bytes: bytes) -> List[dict]:
        """
        Extrai métricas detalhadas de cada caractere para análise forense.
        """
        _, _, img_binary = self.preprocess_metal_image(image_bytes)
        _, filtered, _ = self.process_image(image_bytes, extract_char_images=False)
        
        metrics = []
        
        for idx, (bbox, text, conf) in enumerate(filtered):
            text_clean = ''.join(c for c in text if c.isalnum())
            if not text_clean:
                continue
            
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            
            width = max(xs) - min(xs)
            height = max(ys) - min(ys)
            center_y = (min(ys) + max(ys)) / 2
            
            # ROI para contagem de pontos
            x_min = int(max(0, min(xs)))
            x_max = int(min(img_binary.shape[1], max(xs)))
            y_min = int(max(0, min(ys)))
            y_max = int(min(img_binary.shape[0], max(ys)))
            
            roi = img_binary[y_min:y_max, x_min:x_max]
            
            # Conta pontos (blobs)
            contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            dot_count = len([c for c in contours if cv2.contourArea(c) > 2])
            
            metrics.append({
                'char': text_clean.upper(),
                'index': idx,
                'confidence': conf,
                'width': width,
                'height': height,
                'center_y': center_y,
                'dot_count': dot_count,
                'bbox': bbox
            })
        
        return metrics
