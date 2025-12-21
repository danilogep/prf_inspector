import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from skimage.metrics import structural_similarity as ssim
from app.core.config import settings
from app.core.logger import logger


class FontAnalyzer:
    """
    Analisador de fonte Honda com detecção de vazamentos (gaps).
    
    A fonte Honda tem características específicas que falsificadores 
    frequentemente não conseguem reproduzir:
    
    1. VAZAMENTOS (GAPS): Aberturas específicas em certos números
       - O "4" tem um gap onde a linha vertical não toca a horizontal
       - O "9" tem uma cauda específica
       - O "0" tem proporções exatas
       
    2. PROPORÇÕES: Relação altura/largura específica
    
    3. CANTOS: Ângulos e curvas padronizados
    """
    
    # Características dos números Honda (baseado na imagem de referência)
    # Valores são proporções e características geométricas
    HONDA_FONT_CHARACTERISTICS = {
        '0': {
            'aspect_ratio': (0.55, 0.70),  # largura/altura esperada (min, max)
            'has_internal_gap': False,      # Não tem abertura interna
            'symmetry': 'vertical',         # Simétrico verticalmente
            'corners': 0,                   # Sem cantos (oval)
        },
        '1': {
            'aspect_ratio': (0.20, 0.35),
            'has_base_serif': True,         # Tem serifa na base
            'has_top_serif': True,          # Tem serifa pequena no topo
            'symmetry': 'none',
            'corners': 2,
        },
        '2': {
            'aspect_ratio': (0.50, 0.65),
            'has_internal_gap': False,
            'top_curve': True,              # Curva fechada no topo
            'base_horizontal': True,
            'corners': 1,
        },
        '3': {
            'aspect_ratio': (0.50, 0.65),
            'has_left_gaps': True,          # Aberturas à esquerda
            'center_point': True,           # Ponto central onde curvas se encontram
            'corners': 0,
        },
        '4': {
            'aspect_ratio': (0.55, 0.70),
            'has_critical_gap': True,       # GAP CRÍTICO: linha vertical não toca horizontal
            'gap_position': 'middle',       # Posição do gap
            'symmetry': 'none',
            'corners': 3,
        },
        '5': {
            'aspect_ratio': (0.50, 0.65),
            'top_horizontal': True,
            'bottom_curve_open': True,      # Curva inferior aberta à esquerda
            'corners': 2,
        },
        '6': {
            'aspect_ratio': (0.55, 0.70),
            'top_curve_open': True,         # Curva superior aberta
            'bottom_circle_closed': True,   # Círculo inferior fechado
            'corners': 0,
        },
        '7': {
            'aspect_ratio': (0.50, 0.65),
            'top_horizontal': True,
            'diagonal_clean': True,         # Diagonal sem serifa
            'corners': 1,
        },
        '8': {
            'aspect_ratio': (0.55, 0.70),
            'two_circles': True,
            'top_smaller': True,            # Círculo superior menor
            'symmetry': 'both',
            'corners': 0,
        },
        '9': {
            'aspect_ratio': (0.55, 0.70),
            'top_circle_closed': True,      # Círculo superior fechado
            'tail_curve': True,             # Cauda curva característica
            'corners': 0,
        },
    }
    
    def __init__(self):
        self.font_templates: Dict[str, np.ndarray] = {}
        self.template_features: Dict[str, Dict] = {}
        self._load_font_templates()
    
    def _load_font_templates(self):
        """Carrega templates da fonte Honda."""
        fonts_dir = settings.FONTS_DIR
        
        if not fonts_dir.exists():
            logger.warning(f"Diretório de fontes não encontrado: {fonts_dir}")
            fonts_dir.mkdir(parents=True, exist_ok=True)
            return
        
        # Carrega arquivos individuais (0.png, 1.png, etc.)
        for char in '0123456789ABCDEFGHJKLMNPRSTUVWXYZ':
            for ext in ['.png', '.jpg', '.jpeg']:
                file_path = fonts_dir / f"{char}{ext}"
                if file_path.exists():
                    img = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        self.font_templates[char] = self._normalize_template(img)
                        self.template_features[char] = self._extract_features(img)
                        logger.debug(f"Template carregado: {char}")
                    break
        
        # Tenta carregar spritesheet se existir
        for sprite_name in ['honda_font.png', 'font_template.png', 'numeros.png']:
            sprite_path = fonts_dir / sprite_name
            if sprite_path.exists():
                self._load_spritesheet(sprite_path)
                break
        
        logger.info(f"Total de templates carregados: {len(self.font_templates)}")
    
    def _load_spritesheet(self, file_path: Path):
        """Extrai caracteres de uma spritesheet (imagem com todos os números em sequência)."""
        img = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            logger.error(f"Não foi possível ler spritesheet: {file_path}")
            return
        
        # Binariza
        _, binary = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY_INV)
        
        # Encontra contornos
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filtra contornos pequenos e ordena da esquerda para direita
        valid_contours = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w > 15 and h > 20:  # Filtra ruído
                valid_contours.append((x, y, w, h))
        
        valid_contours.sort(key=lambda b: b[0])
        
        # Assume sequência 0-9
        chars = '0123456789'
        
        for i, (x, y, w, h) in enumerate(valid_contours[:10]):
            if i >= len(chars):
                break
            
            # Adiciona margem
            margin = 3
            y1 = max(0, y - margin)
            y2 = min(img.shape[0], y + h + margin)
            x1 = max(0, x - margin)
            x2 = min(img.shape[1], x + w + margin)
            
            char_img = img[y1:y2, x1:x2]
            char = chars[i]
            
            if char not in self.font_templates:
                self.font_templates[char] = self._normalize_template(char_img)
                self.template_features[char] = self._extract_features(char_img)
                logger.debug(f"Extraído da spritesheet: {char}")
    
    def _normalize_template(self, img: np.ndarray, size: Tuple[int, int] = (64, 80)) -> np.ndarray:
        """Normaliza template para tamanho padrão."""
        h, w = img.shape[:2]
        
        # Calcula escala mantendo proporção
        scale = min(size[0] / w, size[1] / h) * 0.85
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        if new_w < 1 or new_h < 1:
            return np.ones((size[1], size[0]), dtype=np.uint8) * 255
        
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Centraliza em canvas
        canvas = np.ones((size[1], size[0]), dtype=np.uint8) * 255
        y_offset = (size[1] - new_h) // 2
        x_offset = (size[0] - new_w) // 2
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        return canvas
    
    def _extract_features(self, img: np.ndarray) -> Dict:
        """
        Extrai características geométricas do caractere para análise de vazamentos.
        """
        features = {
            'aspect_ratio': 0.0,
            'symmetry_score': 0.0,
            'corner_count': 0,
            'gap_regions': [],
            'contour_area_ratio': 0.0,
        }
        
        # Binariza
        _, binary = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY_INV)
        
        # Encontra contornos
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return features
        
        # Usa o maior contorno
        main_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(main_contour)
        
        # Aspect ratio
        features['aspect_ratio'] = w / max(h, 1)
        
        # Área do contorno vs área do bounding box (indica preenchimento)
        contour_area = cv2.contourArea(main_contour)
        bbox_area = w * h
        features['contour_area_ratio'] = contour_area / max(bbox_area, 1)
        
        # Detecta cantos usando Harris
        gray_float = np.float32(binary)
        corners = cv2.cornerHarris(gray_float, 2, 3, 0.04)
        features['corner_count'] = np.sum(corners > 0.01 * corners.max())
        
        # Simetria vertical
        if w > 10:
            left_half = binary[:, :w//2]
            right_half = cv2.flip(binary[:, w//2:], 1)
            
            # Ajusta tamanhos se necessário
            min_w = min(left_half.shape[1], right_half.shape[1])
            if min_w > 0:
                left_half = left_half[:, :min_w]
                right_half = right_half[:, :min_w]
                
                diff = cv2.absdiff(left_half, right_half)
                features['symmetry_score'] = 1 - (np.sum(diff) / (255 * diff.size))
        
        # Detecta regiões de gap (áreas brancas internas)
        features['gap_regions'] = self._detect_gaps(binary)
        
        return features
    
    def _detect_gaps(self, binary: np.ndarray) -> List[Dict]:
        """
        Detecta gaps/vazamentos no caractere.
        Gaps são regiões brancas que indicam onde as linhas não se conectam.
        """
        gaps = []
        
        # Inverte para encontrar regiões brancas (gaps)
        inverted = cv2.bitwise_not(binary)
        
        # Encontra contornos das regiões brancas internas
        contours, hierarchy = cv2.findContours(
            inverted, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )
        
        if hierarchy is None:
            return gaps
        
        h, w = binary.shape
        
        for i, cnt in enumerate(contours):
            # Verifica se é um contorno interno (não o fundo)
            if hierarchy[0][i][3] != -1:  # Tem pai
                x, y, cw, ch = cv2.boundingRect(cnt)
                area = cv2.contourArea(cnt)
                
                # Calcula posição relativa
                rel_x = (x + cw/2) / w
                rel_y = (y + ch/2) / h
                
                if area > 20:  # Ignora ruído pequeno
                    gaps.append({
                        'position': (rel_x, rel_y),
                        'area': area,
                        'region': 'top' if rel_y < 0.33 else ('middle' if rel_y < 0.66 else 'bottom')
                    })
        
        return gaps
    
    def analyze_character(
        self, 
        char_image: np.ndarray, 
        expected_char: str,
        position: int = 0
    ) -> Dict:
        """
        Analisa um caractere extraído comparando com template e verificando gaps.
        """
        result = {
            'char': expected_char,
            'position': position,
            'similarity_score': 0.0,
            'has_expected_gaps': True,
            'gap_analysis': {},
            'is_suspicious': False,
            'is_high_risk': expected_char in settings.HIGH_RISK_CHARS,
            'issues': []
        }
        
        expected_char = expected_char.upper()
        
        # Se não tiver template, faz análise apenas geométrica
        if expected_char not in self.font_templates:
            result['issues'].append(f"Template para '{expected_char}' não disponível")
            # Faz análise geométrica mesmo sem template
            features = self._extract_features(char_image)
            result['extracted_features'] = features
            return result
        
        template = self.font_templates[expected_char]
        template_features = self.template_features.get(expected_char, {})
        
        # 1. Compara com template (SSIM)
        char_normalized = self._normalize_template(char_image)
        
        try:
            _, template_bin = cv2.threshold(template, 127, 255, cv2.THRESH_BINARY)
            _, char_bin = cv2.threshold(char_normalized, 127, 255, cv2.THRESH_BINARY)
            
            similarity, _ = ssim(template_bin, char_bin, full=True)
            result['similarity_score'] = round(similarity * 100, 1)
        except Exception as e:
            logger.warning(f"Erro no SSIM: {e}")
            result['issues'].append("Erro no cálculo de similaridade")
        
        # 2. Extrai features do caractere atual
        current_features = self._extract_features(char_image)
        result['extracted_features'] = current_features
        
        # 3. Verifica gaps esperados (ANÁLISE DE VAZAMENTOS)
        gap_result = self._verify_gaps(expected_char, current_features, template_features)
        result['gap_analysis'] = gap_result
        result['has_expected_gaps'] = gap_result.get('gaps_match', True)
        
        if not result['has_expected_gaps']:
            result['issues'].append(f"Vazamentos da fonte não correspondem ao esperado")
            result['is_suspicious'] = True
        
        # 4. Verifica proporções
        expected_props = self.HONDA_FONT_CHARACTERISTICS.get(expected_char, {})
        if 'aspect_ratio' in expected_props:
            min_ar, max_ar = expected_props['aspect_ratio']
            actual_ar = current_features.get('aspect_ratio', 0)
            
            if actual_ar < min_ar or actual_ar > max_ar:
                result['issues'].append(
                    f"Proporção incorreta: {actual_ar:.2f} (esperado: {min_ar:.2f}-{max_ar:.2f})"
                )
                result['is_suspicious'] = True
        
        # 5. Threshold de similaridade (mais rigoroso para alto risco)
        threshold = settings.SSIM_THRESHOLD * 100
        if result['is_high_risk']:
            threshold *= 1.15  # 15% mais rigoroso
        
        if result['similarity_score'] < threshold and result['similarity_score'] > 0:
            result['is_suspicious'] = True
            result['issues'].append(
                f"Similaridade {result['similarity_score']:.1f}% abaixo do limiar ({threshold:.1f}%)"
            )
        
        return result
    
    def _verify_gaps(
        self, 
        char: str, 
        current_features: Dict, 
        template_features: Dict
    ) -> Dict:
        """
        Verifica se os gaps/vazamentos do caractere correspondem ao esperado.
        Esta é a análise crucial para detectar falsificações.
        """
        result = {
            'char': char,
            'gaps_match': True,
            'expected_gap_count': 0,
            'detected_gap_count': 0,
            'notes': []
        }
        
        char_props = self.HONDA_FONT_CHARACTERISTICS.get(char, {})
        
        # Verifica gap crítico do "4"
        if char == '4' and char_props.get('has_critical_gap'):
            result['expected_gap_count'] = 1
            current_gaps = current_features.get('gap_regions', [])
            middle_gaps = [g for g in current_gaps if g.get('region') == 'middle']
            result['detected_gap_count'] = len(middle_gaps)
            
            if len(middle_gaps) == 0:
                result['gaps_match'] = False
                result['notes'].append(
                    "⚠️ ALERTA: '4' sem gap característico - possível adulteração de '9' ou '1'"
                )
        
        # Verifica círculos fechados do "0"
        elif char == '0':
            current_gaps = current_features.get('gap_regions', [])
            if len(current_gaps) > 0:
                result['gaps_match'] = False
                result['notes'].append(
                    "⚠️ ALERTA: '0' com aberturas internas - possível adulteração de '6', '8' ou '9'"
                )
        
        # Verifica aberturas do "3"
        elif char == '3' and char_props.get('has_left_gaps'):
            # O 3 deve ter aberturas à esquerda
            current_gaps = current_features.get('gap_regions', [])
            left_gaps = [g for g in current_gaps if g['position'][0] < 0.4]
            
            if len(left_gaps) < 2:
                result['notes'].append(
                    "Verificar: '3' pode ter sido adulterado de '8'"
                )
        
        # Verifica cauda do "9"
        elif char == '9' and char_props.get('tail_curve'):
            current_gaps = current_features.get('gap_regions', [])
            top_gaps = [g for g in current_gaps if g.get('region') == 'top']
            
            # O 9 deve ter o círculo superior fechado
            if len(top_gaps) > 0:
                result['notes'].append(
                    "Verificar: '9' com abertura no topo - possível adulteração"
                )
        
        # Verifica "1" - deve ser estreito
        elif char == '1':
            ar = current_features.get('aspect_ratio', 0)
            if ar > 0.4:  # Muito largo para um "1"
                result['gaps_match'] = False
                result['notes'].append(
                    f"⚠️ ALERTA: '1' muito largo (ratio: {ar:.2f}) - possível adulteração de '7' ou '4'"
                )
        
        return result
    
    def analyze_all_characters(
        self, 
        char_images: List[Tuple[np.ndarray, str, int]]
    ) -> Dict:
        """
        Analisa todos os caracteres extraídos.
        
        Args:
            char_images: Lista de (imagem, caractere, posição)
        """
        results = {
            'total_analyzed': 0,
            'suspicious_count': 0,
            'high_risk_suspicious': 0,
            'gap_issues_count': 0,
            'overall_score': 0.0,
            'characters': [],
            'alerts': []
        }
        
        if not char_images:
            results['alerts'].append("Nenhum caractere para analisar")
            return results
        
        scores = []
        
        for char_img, char_text, position in char_images:
            analysis = self.analyze_character(char_img, char_text, position)
            results['characters'].append(analysis)
            results['total_analyzed'] += 1
            
            if analysis['similarity_score'] > 0:
                scores.append(analysis['similarity_score'])
            
            if analysis['is_suspicious']:
                results['suspicious_count'] += 1
                
                if analysis['is_high_risk']:
                    results['high_risk_suspicious'] += 1
                    results['alerts'].append(
                        f"⚠️ Caractere de ALTO RISCO '{analysis['char']}' (pos {position}) suspeito"
                    )
            
            if not analysis['has_expected_gaps']:
                results['gap_issues_count'] += 1
            
            # Adiciona notas do gap_analysis aos alertas
            gap_notes = analysis.get('gap_analysis', {}).get('notes', [])
            results['alerts'].extend(gap_notes)
        
        if scores:
            results['overall_score'] = round(sum(scores) / len(scores), 1)
        
        return results
    
    def get_available_templates(self) -> List[str]:
        """Retorna caracteres com template disponível."""
        return list(self.font_templates.keys())
