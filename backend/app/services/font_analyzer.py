"""
Analisador de fonte Honda para detecção de adulteração.
Compara caracteres extraídos com templates da fonte oficial.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from app.core.logger import logger
from app.core.config import settings


class FontAnalyzer:
    """
    Analisa caracteres comparando com templates da fonte Honda.
    
    Características verificadas:
    - Proporção (aspect ratio)
    - Similaridade estrutural
    - Vazamentos/gaps característicos
    """
    
    # Características esperadas da fonte Honda por caractere
    HONDA_FONT_CHARACTERISTICS = {
        '0': {
            'aspect_ratio_range': (0.55, 0.75),
            'has_internal_gap': False,
            'description': 'Oval fechada, sem cortes internos'
        },
        '1': {
            'aspect_ratio_range': (0.20, 0.40),
            'has_internal_gap': False,
            'description': 'Fino, base reta, serifa pequena no topo'
        },
        '2': {
            'aspect_ratio_range': (0.50, 0.70),
            'has_internal_gap': False,
            'description': 'Curva superior, base horizontal'
        },
        '3': {
            'aspect_ratio_range': (0.50, 0.70),
            'has_internal_gap': True,
            'expected_gaps': ['left_top', 'left_bottom'],
            'description': 'Duas curvas abertas à esquerda'
        },
        '4': {
            'aspect_ratio_range': (0.55, 0.75),
            'has_internal_gap': True,
            'expected_gaps': ['middle'],
            'description': 'Gap no encontro das linhas - característica Honda'
        },
        '5': {
            'aspect_ratio_range': (0.50, 0.70),
            'has_internal_gap': False,
            'description': 'Topo horizontal, curva inferior'
        },
        '6': {
            'aspect_ratio_range': (0.55, 0.75),
            'has_internal_gap': False,
            'description': 'Curva superior aberta, círculo inferior'
        },
        '7': {
            'aspect_ratio_range': (0.50, 0.70),
            'has_internal_gap': False,
            'description': 'Linha horizontal no topo, diagonal'
        },
        '8': {
            'aspect_ratio_range': (0.55, 0.75),
            'has_internal_gap': False,
            'description': 'Dois círculos empilhados'
        },
        '9': {
            'aspect_ratio_range': (0.55, 0.75),
            'has_internal_gap': False,
            'description': 'Círculo superior, cauda curva'
        },
    }
    
    # Caracteres de alto risco (mais falsificados)
    HIGH_RISK_CHARS = ['0', '1', '3', '4', '9']
    
    def __init__(self):
        self.templates: Dict[str, np.ndarray] = {}
        self._load_font_templates()
    
    def _load_font_templates(self):
        """Carrega templates de fonte do diretório."""
        fonts_dir = Path(settings.FONTS_DIR)
        
        if not fonts_dir.exists():
            logger.warning(f"Diretório de fontes não encontrado: {fonts_dir}")
            return
        
        for char in '0123456789ABCDEFGHJKLMNPRSTUVWXYZ':
            template_path = fonts_dir / f"{char}.png"
            if template_path.exists():
                img = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    # Normaliza para tamanho padrão
                    img = cv2.resize(img, (50, 70))
                    _, img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
                    self.templates[char] = img
        
        logger.info(f"Templates carregados: {len(self.templates)} caracteres")
    
    def get_available_templates(self) -> List[str]:
        """Retorna lista de caracteres com template disponível."""
        return list(self.templates.keys())
    
    def analyze_character(
        self, 
        char_image: np.ndarray, 
        expected_char: str
    ) -> Dict:
        """
        Analisa um caractere extraído.
        
        Args:
            char_image: Imagem do caractere (grayscale)
            expected_char: Caractere esperado
            
        Returns:
            Dict com análise detalhada
        """
        result = {
            'char': expected_char,
            'similarity_score': 0.0,
            'has_expected_gaps': True,
            'gap_analysis': {},
            'is_suspicious': False,
            'is_high_risk': expected_char in self.HIGH_RISK_CHARS,
            'issues': [],
            'extracted_features': {}
        }
        
        if char_image is None or char_image.size == 0:
            result['issues'].append("Imagem do caractere inválida")
            return result
        
        # Extrai características
        features = self._extract_features(char_image)
        result['extracted_features'] = features
        
        # Compara com template
        if expected_char in self.templates:
            similarity = self._compare_with_template(char_image, expected_char)
            result['similarity_score'] = round(similarity * 100, 1)
            
            if similarity < 0.6:
                result['is_suspicious'] = True
                result['issues'].append(f"Baixa similaridade com template: {similarity:.1%}")
        else:
            result['issues'].append(f"Template para '{expected_char}' não disponível")
        
        # Verifica características esperadas
        if expected_char in self.HONDA_FONT_CHARACTERISTICS:
            char_specs = self.HONDA_FONT_CHARACTERISTICS[expected_char]
            
            # Verifica proporção
            ar_min, ar_max = char_specs['aspect_ratio_range']
            if not (ar_min <= features['aspect_ratio'] <= ar_max):
                result['is_suspicious'] = True
                result['issues'].append(
                    f"Proporção incorreta: {features['aspect_ratio']:.2f} "
                    f"(esperado: {ar_min:.2f}-{ar_max:.2f})"
                )
            
            # Verifica gaps
            if char_specs.get('has_internal_gap'):
                gap_result = self._verify_gaps(char_image, expected_char)
                result['gap_analysis'] = gap_result
                if not gap_result.get('gaps_match', True):
                    result['has_expected_gaps'] = False
                    result['issues'].append("Vazamentos da fonte não correspondem ao esperado")
        
        return result
    
    def _extract_features(self, char_image: np.ndarray) -> Dict:
        """Extrai características de um caractere."""
        # Garante binário
        if len(char_image.shape) == 3:
            char_image = cv2.cvtColor(char_image, cv2.COLOR_BGR2GRAY)
        
        _, binary = cv2.threshold(char_image, 127, 255, cv2.THRESH_BINARY)
        
        # Proporção
        h, w = binary.shape
        aspect_ratio = w / h if h > 0 else 0
        
        # Simetria horizontal
        left_half = binary[:, :w//2]
        right_half = cv2.flip(binary[:, w//2:], 1)
        
        min_w = min(left_half.shape[1], right_half.shape[1])
        if min_w > 0:
            left_half = left_half[:, :min_w]
            right_half = right_half[:, :min_w]
            symmetry = 1 - np.sum(np.abs(left_half.astype(float) - right_half.astype(float))) / (255 * h * min_w)
        else:
            symmetry = 0
        
        # Contagem de cantos
        corners = cv2.goodFeaturesToTrack(binary, 100, 0.01, 5)
        corner_count = len(corners) if corners is not None else 0
        
        # Regiões de gap
        gap_regions = self._find_gap_regions(binary)
        
        # Área relativa
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            main_contour = max(contours, key=cv2.contourArea)
            contour_area = cv2.contourArea(main_contour)
            total_area = h * w
            area_ratio = contour_area / total_area if total_area > 0 else 0
        else:
            area_ratio = 0
        
        return {
            'aspect_ratio': float(aspect_ratio),
            'symmetry_score': float(symmetry),
            'corner_count': int(corner_count),
            'gap_regions': gap_regions,
            'contour_area_ratio': float(area_ratio)
        }
    
    def _find_gap_regions(self, binary: np.ndarray) -> List[Dict]:
        """Encontra regiões de gap (vazamentos) no caractere."""
        gaps = []
        
        # Inverte para encontrar buracos
        inverted = cv2.bitwise_not(binary)
        contours, _ = cv2.findContours(inverted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        h, w = binary.shape
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 20:  # Ignora ruído
                M = cv2.moments(contour)
                if M['m00'] > 0:
                    cx = M['m10'] / M['m00']
                    cy = M['m01'] / M['m00']
                    
                    # Determina região
                    region = 'middle'
                    if cy < h * 0.33:
                        region = 'top'
                    elif cy > h * 0.66:
                        region = 'bottom'
                    
                    gaps.append({
                        'position': (float(cx / w), float(cy / h)),
                        'area': float(area),
                        'region': region
                    })
        
        return gaps
    
    def _compare_with_template(self, char_image: np.ndarray, char: str) -> float:
        """Compara caractere com template usando múltiplos métodos."""
        if char not in self.templates:
            return 0.0
        
        template = self.templates[char]
        
        # Prepara imagem
        if len(char_image.shape) == 3:
            char_image = cv2.cvtColor(char_image, cv2.COLOR_BGR2GRAY)
        
        # Redimensiona para tamanho do template
        char_resized = cv2.resize(char_image, (template.shape[1], template.shape[0]))
        _, char_binary = cv2.threshold(char_resized, 127, 255, cv2.THRESH_BINARY)
        
        # Método 1: Correlação normalizada
        result = cv2.matchTemplate(char_binary, template, cv2.TM_CCOEFF_NORMED)
        correlation = float(result[0][0]) if result.size > 0 else 0
        
        # Método 2: Diferença de pixels
        diff = np.abs(char_binary.astype(float) - template.astype(float))
        pixel_similarity = 1 - np.mean(diff) / 255
        
        # Combina métodos
        similarity = 0.6 * max(0, correlation) + 0.4 * pixel_similarity
        
        return min(1.0, max(0.0, similarity))
    
    def _verify_gaps(self, char_image: np.ndarray, char: str) -> Dict:
        """Verifica se os gaps característicos estão presentes."""
        result = {
            'char': char,
            'gaps_match': True,
            'expected_gap_count': 0,
            'detected_gap_count': 0,
            'notes': []
        }
        
        if char not in self.HONDA_FONT_CHARACTERISTICS:
            return result
        
        specs = self.HONDA_FONT_CHARACTERISTICS[char]
        
        if not specs.get('has_internal_gap'):
            return result
        
        # Extrai gaps
        if len(char_image.shape) == 3:
            char_image = cv2.cvtColor(char_image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(char_image, 127, 255, cv2.THRESH_BINARY)
        
        gaps = self._find_gap_regions(binary)
        
        expected_gaps = specs.get('expected_gaps', [])
        result['expected_gap_count'] = len(expected_gaps)
        result['detected_gap_count'] = len(gaps)
        
        # Verifica específicos por caractere
        if char == '4':
            # O "4" Honda tem gap no meio onde as linhas se encontram
            middle_gaps = [g for g in gaps if g['region'] == 'middle']
            if not middle_gaps:
                result['gaps_match'] = False
                result['notes'].append("Gap central do '4' não detectado - possível adulteração")
        
        elif char == '3':
            # O "3" tem duas aberturas à esquerda
            if len(gaps) < 2:
                result['gaps_match'] = False
                result['notes'].append("Aberturas do '3' não detectadas corretamente")
        
        return result
    
    def analyze_all_characters(
        self, 
        char_images: List[Tuple[np.ndarray, str, int]]
    ) -> Dict:
        """
        Analisa todos os caracteres extraídos.
        
        Args:
            char_images: Lista de (imagem, caractere, posição)
            
        Returns:
            Dict com análise completa
        """
        results = {
            'characters': [],
            'alerts': [],
            'high_risk_count': 0,
            'suspicious_count': 0
        }
        
        for img, char, position in char_images:
            analysis = self.analyze_character(img, char)
            analysis['position'] = position
            results['characters'].append(analysis)
            
            if analysis['is_high_risk']:
                results['high_risk_count'] += 1
                if analysis['is_suspicious']:
                    results['alerts'].append(
                        f"⚠️ Caractere de ALTO RISCO '{char}' (pos {position}) suspeito"
                    )
            
            if analysis['is_suspicious']:
                results['suspicious_count'] += 1
            
            # Alertas específicos de gap
            for note in analysis.get('gap_analysis', {}).get('notes', []):
                results['alerts'].append(note)
        
        return results