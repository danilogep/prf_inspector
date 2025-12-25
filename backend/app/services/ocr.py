"""
OCR Engine v3.0 - Otimizado para Motor Honda
=============================================
Correções baseadas em CONTEXTO dos prefixos Honda:

REGRA CRÍTICA - Posição 2 do prefixo:
- Prefixos Honda: ND, MD, MC, NC, JC, JF, JK, PC, KY
- Posição 2 é SEMPRE: D, C, F, K, Y (consoantes)
- NUNCA é "O" na posição 2!

Portanto: NO → ND, MO → MD, etc.
"""

import cv2
import numpy as np
import easyocr
import os
import base64
import re
from typing import Tuple, List, Optional, Dict
from app.core.logger import logger
from app.core.config import settings


class OCREngine:
    """Motor de OCR otimizado para gravações Honda."""
    
    # Prefixos Honda conhecidos (2 primeiras letras)
    HONDA_PREFIX_STARTS = ['ND', 'MD', 'MC', 'NC', 'JC', 'JF', 'JK', 'PC', 'KY']
    
    # Prefixos completos conhecidos
    KNOWN_PREFIXES = [
        'ND09E1', 'MD09E1', 'MD09E', 'ND09E',
        'MC27E', 'MC41E', 'MC38E', 'MC52E', 'MC65E',
        'MD37E', 'MD38E', 'MD44E',
        'NC51E', 'NC56E', 'NC70E', 'NC75E',
        'JC30E', 'JC75E', 'JC79E',
        'JF77E', 'JF81E', 'JF83E',
        'PC40E', 'PC44E',
        'JK12E',
        'KYJ',
    ]
    
    # Mapeamento de correções por posição
    # Posição 2: O→D, 0→D (nunca é O ou 0)
    # Posições 3,4: sempre números
    # Posição 5: E (letra)
    # Posição 6: número (se existir)
    
    def __init__(self, use_gpu: bool = False):
        logger.info("Inicializando OCR Engine v3.0...")
        self.reader = easyocr.Reader(['en'], gpu=use_gpu, verbose=False)
        self.confidence_threshold = 0.3
        
        # Claude Vision para fallback - usa config que carrega do .env
        self.claude_api_key = settings.ANTHROPIC_API_KEY
        self.use_claude = bool(self.claude_api_key)
        
        if self.use_claude:
            logger.info(f"✓ Claude Vision disponível para OCR (key: {self.claude_api_key[:20]}...)")
        
        logger.info("OCR Engine v3.0 pronto")
    
    def process_image(
        self,
        image_bytes: bytes,
        extract_char_images: bool = True,
        force_claude: bool = False
    ) -> Tuple[str, List, Optional[List]]:
        """
        Processa imagem e extrai número do motor.
        
        Pipeline:
        1. OCR EasyOCR (3 passagens)
        2. Reorganização (prefixo primeiro)
        3. Correção baseada em contexto Honda
        4. Claude Vision se necessário
        """
        try:
            # Pré-processamento
            img_color, img_gray, img_binary, img_contrast = self._preprocess(image_bytes)
            
            # 1. OCR em múltiplas passagens
            texts = []
            
            # Original
            result1 = self.reader.readtext(image_bytes, detail=1)
            text1 = self._extract_text(result1)
            if text1:
                texts.append(text1)
                logger.info(f"OCR original: '{text1}'")
            
            # Contraste melhorado
            _, contrast_enc = cv2.imencode('.jpg', img_contrast)
            result2 = self.reader.readtext(contrast_enc.tobytes(), detail=1)
            text2 = self._extract_text(result2)
            if text2 and text2 != text1:
                texts.append(text2)
                logger.info(f"OCR contraste: '{text2}'")
            
            # Binário
            _, binary_enc = cv2.imencode('.jpg', img_binary)
            result3 = self.reader.readtext(binary_enc.tobytes(), detail=1)
            text3 = self._extract_text(result3)
            if text3 and text3 not in texts:
                texts.append(text3)
                logger.info(f"OCR binário: '{text3}'")
            
            # 2. Combina e reorganiza
            combined = self._combine_texts(texts)
            logger.info(f"Combinado: '{combined}'")
            
            # 3. Reorganiza (prefixo primeiro)
            reorganized = self._reorganize_honda_format(combined)
            logger.info(f"Reorganizado: '{reorganized}'")
            
            # 4. Correção baseada em contexto Honda
            corrected = self._apply_honda_corrections(reorganized)
            logger.info(f"Corrigido: '{corrected}'")
            
            # 5. Verifica se precisa Claude
            needs_claude = force_claude or not self._is_valid_format(corrected)
            
            if needs_claude and self.use_claude:
                logger.info("Acionando Claude Vision para verificação...")
                claude_result = self._ocr_with_claude(image_bytes)
                if claude_result:
                    corrected = claude_result
                    logger.info(f"Claude Vision: '{corrected}'")
            
            logger.info(f"Final: '{corrected}'")
            
            # Extrai imagens de caracteres
            char_images = None
            if extract_char_images:
                char_images = self._extract_char_images(img_gray, result1)
            
            return corrected, result1, char_images
            
        except Exception as e:
            logger.error(f"Erro OCR: {e}")
            raise
    
    def _preprocess(self, image_bytes: bytes) -> Tuple[np.ndarray, ...]:
        """Pré-processamento da imagem."""
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("Falha ao decodificar imagem")
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # CLAHE para contraste
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        
        # Bilateral filter
        denoised = cv2.bilateralFilter(contrast, 9, 75, 75)
        
        # Threshold adaptativo
        binary = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=15, C=4
        )
        
        return img, gray, binary, contrast
    
    def _extract_text(self, results: List) -> str:
        """Extrai texto dos resultados do OCR."""
        if not results:
            return ""
        
        # Ordena por posição Y, depois X
        sorted_results = sorted(results, key=lambda x: (
            min(p[1] for p in x[0]),
            min(p[0] for p in x[0])
        ))
        
        text = ""
        for bbox, txt, conf in sorted_results:
            if conf >= self.confidence_threshold:
                clean = ''.join(c for c in txt if c.isalnum())
                text += clean
        
        return text.upper()
    
    def _combine_texts(self, texts: List[str]) -> str:
        """Combina múltiplas leituras OCR."""
        if not texts:
            return ""
        
        # Usa o texto mais longo que parece válido
        best = ""
        for text in texts:
            if len(text) > len(best):
                best = text
        
        return best
    
    def _reorganize_honda_format(self, text: str) -> str:
        """
        Reorganiza texto para formato Honda: PREFIXO + SERIAL.
        
        O OCR pode ler na ordem errada (serial primeiro).
        Esta função detecta o prefixo e move para o início.
        """
        if not text or len(text) < 10:
            return text
        
        # Gera variantes do texto com possíveis erros OCR
        variants = self._generate_ocr_variants(text)
        
        # Procura prefixo conhecido em qualquer posição
        for variant in variants:
            for prefix in self.KNOWN_PREFIXES:
                # Gera variantes do prefixo também
                prefix_variants = self._generate_prefix_variants(prefix)
                
                for pv in prefix_variants:
                    if pv in variant:
                        idx = variant.index(pv)
                        if idx > 0:
                            # Prefixo não está no início - reorganiza
                            before = variant[:idx]
                            after = variant[idx + len(pv):]
                            # Prefixo + resto
                            reorganized = pv + before + after
                            return reorganized
                        return variant
        
        return text
    
    def _generate_ocr_variants(self, text: str) -> List[str]:
        """Gera variantes considerando erros comuns de OCR."""
        variants = [text]
        
        # O ↔ 0
        variants.append(text.replace('O', '0'))
        variants.append(text.replace('0', 'O'))
        
        # I ↔ 1
        v2 = text.replace('I', '1')
        variants.append(v2)
        variants.append(v2.replace('O', '0'))
        
        return variants
    
    def _generate_prefix_variants(self, prefix: str) -> List[str]:
        """Gera variantes do prefixo com erros OCR."""
        variants = [prefix]
        
        # D pode ser lido como O ou 0
        if 'D' in prefix:
            variants.append(prefix.replace('D', 'O'))
            variants.append(prefix.replace('D', '0'))
        
        # 0 pode ser lido como O ou D
        if '0' in prefix:
            variants.append(prefix.replace('0', 'O'))
        
        # 1 pode ser lido como I ou l
        if '1' in prefix:
            variants.append(prefix.replace('1', 'I'))
            variants.append(prefix.replace('1', 'l'))
        
        return variants
    
    def _apply_honda_corrections(self, text: str) -> str:
        """
        Aplica correções baseadas no CONTEXTO dos prefixos Honda.
        
        REGRAS CRÍTICAS:
        - Posição 1: M, N, J, P, K (letras)
        - Posição 2: D, C, F, K, Y (NUNCA é O ou 0!)
        - Posições 3,4: números (09, 27, 37, etc)
        - Posição 5: E (letra)
        - Posição 6: número ou nada
        - Serial: letra + 6 números
        """
        if not text or len(text) < 6:
            return text
        
        result = list(text)
        
        # === CORREÇÃO POSIÇÃO 2: O/0 → D ou C ===
        if len(result) >= 2:
            char2 = result[1]
            char1 = result[0]
            
            # Se posição 2 é O ou 0, corrige baseado na posição 1
            if char2 in ['O', '0']:
                if char1 in ['N', 'M']:
                    # ND, MD são os mais comuns
                    result[1] = 'D'
                    logger.info(f"Correção posição 2: '{char2}' → 'D' (contexto: {char1}D)")
                elif char1 in ['J', 'P', 'N']:
                    # JC, PC, NC
                    result[1] = 'C'
                    logger.info(f"Correção posição 2: '{char2}' → 'C' (contexto: {char1}C)")
        
        # === CORREÇÃO POSIÇÕES 3,4: devem ser números ===
        if len(result) >= 4:
            # Posição 3
            if result[2] == 'O':
                result[2] = '0'
                logger.info("Correção posição 3: 'O' → '0'")
            elif result[2] == 'I':
                result[2] = '1'
                logger.info("Correção posição 3: 'I' → '1'")
            
            # Posição 4
            if result[3] == 'O':
                result[3] = '0'
                logger.info("Correção posição 4: 'O' → '0'")
            elif result[3] == 'I':
                result[3] = '1'
                logger.info("Correção posição 4: 'I' → '1'")
        
        # === CORREÇÃO POSIÇÃO 6: se existe, deve ser número ===
        if len(result) >= 6:
            if result[5] == 'I':
                result[5] = '1'
                logger.info("Correção posição 6: 'I' → '1'")
            elif result[5] == 'O':
                result[5] = '0'
                logger.info("Correção posição 6: 'O' → '0'")
        
        # === CORREÇÃO NO SERIAL (posições 7+) ===
        # Serial típico: B215797 (1 letra + 6 números)
        if len(result) >= 13:
            # Posições 8-13 devem ser números
            for i in range(7, min(14, len(result))):
                if result[i] == 'O':
                    result[i] = '0'
                elif result[i] == 'I':
                    result[i] = '1'
        
        return ''.join(result)
    
    def _is_valid_format(self, text: str) -> bool:
        """Verifica se o formato é válido para Honda."""
        if not text or len(text) < 10:
            return False
        
        # Verifica se começa com prefixo conhecido
        for prefix in self.KNOWN_PREFIXES:
            if text.startswith(prefix):
                return True
        
        # Verifica padrão geral
        pattern = r'^[MNJPK][DC][0-9]{2}E[0-9]?[A-Z]?[0-9]{6,7}$'
        return bool(re.match(pattern, text))
    
    def _ocr_with_claude(self, image_bytes: bytes) -> Optional[str]:
        """OCR usando Claude Vision como fallback."""
        if not self.use_claude:
            return None
        
        try:
            import httpx
            
            b64 = base64.b64encode(image_bytes).decode()
            media_type = "image/jpeg"
            
            prompt = """Leia o número de motor Honda nesta imagem.

FORMATO ESPERADO:
- Prefixo (6 chars): Ex: ND09E1, MD09E1, MC27E
- Serial (7 chars): Ex: B215797

ATENÇÃO:
- Use 0 (zero), não O (letra)
- Use 1 (um), não I (letra)
- Posição 2 é D ou C, nunca O
- N tem diagonal única, M tem dois picos

Responda APENAS com o código completo, sem explicações.
Exemplo: ND09E1B215797"""

            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 100,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                            {"type": "text", "text": prompt}
                        ]
                    }]
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                content = response.json()['content'][0]['text']
                # Extrai apenas alfanuméricos
                code = re.sub(r'[^A-Z0-9]', '', content.upper())
                return code if len(code) >= 10 else None
            
            return None
            
        except Exception as e:
            logger.error(f"Erro Claude OCR: {e}")
            return None
    
    def _extract_char_images(self, img_gray: np.ndarray, results: List) -> List:
        """Extrai imagens individuais de caracteres."""
        char_images = []
        position = 0
        
        for bbox, text, conf in results:
            if conf < self.confidence_threshold:
                continue
            
            xs = [int(p[0]) for p in bbox]
            ys = [int(p[1]) for p in bbox]
            
            x_min = max(0, min(xs) - 3)
            x_max = min(img_gray.shape[1], max(xs) + 3)
            y_min = max(0, min(ys) - 3)
            y_max = min(img_gray.shape[0], max(ys) + 3)
            
            roi = img_gray[y_min:y_max, x_min:x_max]
            if roi.size == 0:
                continue
            
            text_clean = ''.join(c for c in text if c.isalnum())
            
            for char in text_clean:
                position += 1
                char_images.append((roi.copy(), char.upper(), position))
        
        return char_images
    
    def get_character_metrics(self, image_bytes: bytes) -> List[Dict]:
        """Extrai métricas dos caracteres."""
        _, _, img_binary, _ = self._preprocess(image_bytes)
        _, results, _ = self.process_image(image_bytes, extract_char_images=False)
        
        metrics = []
        for idx, item in enumerate(results or []):
            if len(item) < 3:
                continue
            bbox, text, conf = item
            
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            
            metrics.append({
                'char': text.upper(),
                'index': idx,
                'confidence': conf,
                'width': max(xs) - min(xs),
                'height': max(ys) - min(ys),
                'center_y': (min(ys) + max(ys)) / 2
            })
        
        return metrics
